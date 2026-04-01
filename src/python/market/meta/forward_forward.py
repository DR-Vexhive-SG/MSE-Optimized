# src/python/market/meta/forward_forward.py
"""
Forward-Forward Algorithm - MSE v5.0.2-R (Q5, Q6, Q11)
======================================================

Implementación del algoritmo Forward-Forward de Hinton como meta-patrón importable.
Se activa automáticamente ante estancamiento del sistema.

Conexión Formal:
- Q5: Mapeo Estructural FF ↔ MSE
- Q6: FF como meta-patrón importable vía Ψ
- Q11: Activación por estancamiento (backtracks > umbral, progreso = 0)

Referencia: Hinton, G. (2022). "The Forward-Forward Algorithm: Some Preliminary Investigations"
"""

import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import sys
import time

# Asegurar paths
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.python.market.market_pattern_database import MarketPatternDatabase, MarketStoredPattern
from src.python.market.axioms import MarketRegime


@dataclass
class FFConfig:
    """
    Configuración del Forward-Forward (Q5, Q6).

    Parámetros que controlan el comportamiento del FF.
    """
    # 1D.2: Temperature adjustment for more exploitation (1.0098 → 0.92)
    temperature: float = 0.92  # 1D.2: 1.0098 → 0.92 (more exploitation, less exploration)

    # Umbrales de activación (Q11)
    stagnation_backtracks_threshold: int = 50  # Backtracks mínimos para considerar estancamiento
    stagnation_window: int = 50  # Ventana de barras sin progreso
    stagnation_min_trades: int = 5  # Trades mínimos en ventana para evaluar

    # Parámetros de aprendizaje FF
    positive_pass_multiplier: float = 2.0  # Multiplicador para δ⁺ en positive pass
    negative_pass_multiplier: float = 2.0  # Multiplicador para δ⁻ en negative pass
    ff_learning_rate: float = 0.15  # Tasa de aprendizaje FF (más alta que REINFORCE normal)

    # Configuración de datos corruptos (negative pass)
    corruption_rate: float = 0.10  # 10% de datos corruptos para negative pass
    corruption_types: List[str] = field(default_factory=lambda: ['price_noise', 'label_flip'])

    # Límites
    max_ff_iterations: int = 10  # Máximo de iteraciones FF por activación
    min_confidence_change: float = 0.01  # Cambio mínimo de confianza para continuar
    
    # =========================================================================
    # 🆕 Q7: SELECTIVIDAD DE FF (FF por subproblemas específicos)
    # =========================================================================
    # FF selectivo por régimen (no global)
    enable_regime_selectivity: bool = True  # Activar FF selectivo por régimen
    regimes_for_ff: List[str] = field(default_factory=lambda: ['LATERAL'])  # Regímenes donde aplicar FF
    # LATERAL es el principal candidato: más estancamientos, patrones range-bound
    
    # FF selectivo por tipo de patrón
    enable_pattern_selectivity: bool = True  # Activar FF solo para patrones específicos
    pattern_types_for_ff: List[str] = field(default_factory=lambda: [
        'range_buy_low', 'range_sell_high',  # LATERAL patterns (más estancamientos)
        'head_and_shoulders', 'inverse_head_and_shoulders'  # Reversal patterns (alta complejidad)
    ])
    
    # Umbrales específicos por régimen
    regime_specific_thresholds: Dict[str, int] = field(default_factory=lambda: {
        'LATERAL': 40,  # Menor umbral para LATERAL (más propenso a estancamiento)
        'BULL': 60,     # Mayor umbral para BULL (menos estancamientos)
        'BEAR': 60      # Mayor umbral para BEAR (menos estancamientos)
    })


@dataclass
class FFEpisode:
    """
    Episodio de entrenamiento Forward-Forward.
    """
    timestamp: float
    mode: str  # 'positive' o 'negative'
    patterns_used: List[str]
    outcome: str  # 'success' o 'failure'
    confidence_changes: Dict[str, float]
    goodness_score: float


class ForwardForwardLearner:
    """
    Implementación del algoritmo Forward-Forward para MSE Trading.
    
    Formalización (Q5 - Mapeo Estructural):
    
    | Concepto FF          | Equivalente MSE              | Función                           |
    |---------------------|------------------------------|-----------------------------------|
    | Positive Pass       | Resolución Exitosa           | Maximiza score de patrones útiles |
    | Negative Pass       | Backtrack / Fallo            | Minimiza score de patrones dañinos|
    | Goodness Function   | Score(i,j)                   | Evalúa "bondad" local             |
    | Capa Neuronal       | Patrón Individual            | Actualiza E(pt) localmente        |
    
    Q6: FF es importable como meta-patrón cuando Ψ.ff_importable = True
    
    Q11: Se activa automáticamente cuando:
      - backtracks > stagnation_backtracks_threshold
      - progreso = 0 por stagnation_window barras
    """
    
    def __init__(self, pattern_db: MarketPatternDatabase,
                 config: Optional[FFConfig] = None):
        """
        Inicializar aprendiz Forward-Forward.
        
        Args:
            pattern_db: Base de datos de patrones para actualizar E(pt)
            config: Configuración de FF (default: FFConfig())
        """
        self.pattern_db = pattern_db
        self.config = config or FFConfig()
        
        # Historial de episodios FF
        self.episodes: List[FFEpisode] = []
        
        # Estadísticas
        self.stats = {
            'total_activations': 0,
            'total_positive_passes': 0,
            'total_negative_passes': 0,
            'patterns_updated': 0,
            'last_activation_timestamp': None,
            'avg_goodness_positive': 0.0,
            'avg_goodness_negative': 0.0
        }
        
        # Estado actual
        self.is_active: bool = False
        self.current_iteration: int = 0
        self.stagnation_detected: bool = False
    
    # ========================================================================
    # Q11: DETECCIÓN DE ESTANCAMIENTO
    # ========================================================================

    def check_stagnation(self, backtracks: int,
                        progress: int,
                        recent_trades: List[Dict[str, Any]],
                        window: int = None,
                        current_regime: str = None,
                        active_patterns: List[str] = None) -> bool:
        """
        Q11 + Q7: Detectar estancamiento para activar FF con selectividad.

        Criterios de estancamiento:
        1. backtracks > stagnation_backtracks_threshold (ajustado por régimen)
        2. progreso = 0 por stagnation_window barras
        3. trades recientes con win_rate < 30%
        4. Q7: Régimen debe estar en regimes_for_ff
        5. Q7: Patrones activos deben estar en pattern_types_for_ff

        Args:
            backtracks: Número total de backtracks
            progress: Progreso en ventana actual (0 = sin progreso)
            recent_trades: Lista de trades recientes con 'pnl' y 'timestamp'
            window: Ventana de evaluación (default: config.stagnation_window)
            current_regime: Régimen actual (BULL/BEAR/LATERAL)
            active_patterns: Lista de tipos de patrones activos

        Returns:
            bool: True si se detecta estancamiento Y FF está habilitado para este régimen/patrones
        """
        if window is None:
            window = self.config.stagnation_window

        # =========================================================================
        # Q7: SELECTIVIDAD POR RÉGIMEN
        # =========================================================================
        if self.config.enable_regime_selectivity and current_regime:
            if current_regime not in self.config.regimes_for_ff:
                # FF no está habilitado para este régimen
                return False
            
            # Usar umbral específico por régimen
            regime_threshold = self.config.regime_specific_thresholds.get(
                current_regime, 
                self.config.stagnation_backtracks_threshold
            )
        else:
            regime_threshold = self.config.stagnation_backtracks_threshold
        
        # =========================================================================
        # Q7: SELECTIVIDAD POR TIPO DE PATRÓN
        # =========================================================================
        if self.config.enable_pattern_selectivity and active_patterns:
            # Verificar si algún patrón activo está en la lista de patrones para FF
            has_ff_pattern = any(p in self.config.pattern_types_for_ff for p in active_patterns)
            if not has_ff_pattern:
                # FF no está habilitado para estos patrones
                return False
        
        # Criterio 1: Backtracks excesivos (ajustado por régimen)
        if backtracks <= regime_threshold:
            return False

        # Criterio 2: Sin progreso
        if progress > 0:
            return False

        # Criterio 3: Win rate bajo en trades recientes
        if len(recent_trades) >= self.config.stagnation_min_trades:
            winning_trades = sum(1 for t in recent_trades if t.get('pnl', 0) > 0)
            win_rate = winning_trades / len(recent_trades)

            if win_rate >= 0.30:
                return False  # Win rate aceptable, no es estancamiento

        # Estancamiento confirmado + Q7 selectividad verificada
        self.stagnation_detected = True
        self.stats['total_activations'] += 1
        self.stats['last_activation_timestamp'] = time.time()
        
        # Log Q7
        if self.config.enable_regime_selectivity:
            print(f"[FF-Q7] 🚨 Estancamiento detectado en régimen '{current_regime}' (umbral: {regime_threshold})")
        if self.config.enable_pattern_selectivity:
            print(f"[FF-Q7]    Patrones elegibles: {self.config.pattern_types_for_ff}")

        return True
    
    def activate_ff(self):
        """
        Activar modo Forward-Forward.
        """
        self.is_active = True
        self.current_iteration = 0
        print(f"[FF] 🚀 Forward-Forward ACTIVADO por estancamiento")
    
    def deactivate_ff(self):
        """
        Desactivar modo Forward-Forward.
        """
        self.is_active = False
        self.current_iteration = 0
        print(f"[FF] ✅ Forward-Forward DESACTIVADO")
    
    # ========================================================================
    # Q5: MAPEO ESTRUCTURAL FF ↔ MSE
    # ========================================================================
    
    def positive_pass(self, successful_patterns: List[MarketStoredPattern],
                     goodness_score: float = 1.0) -> Dict[str, float]:
        """
        Q5: Positive Pass - Maximizar score de patrones exitosos.
        
        Análogo a FF positive pass con datos reales.
        
        Formalización:
          Para cada patrón exitoso p:
            E(p) ← E(p) + δ⁺ × ff_learning_rate × positive_pass_multiplier
            goodness(p) = score(p) / max_score
        
        Args:
            successful_patterns: Lista de patrones que llevaron a éxito
            goodness_score: Score de bondad [0, 1]
        
        Returns:
            Dict[str, float]: Cambios de confianza por patrón
        """
        confidence_changes = {}
        
        for pattern in successful_patterns:
            old_confidence = pattern.confidence
            
            # Actualizar E(pt) con multiplicador FF
            delta = (
                self.config.ff_learning_rate *
                self.config.positive_pass_multiplier *
                goodness_score
            )
            
            # Aplicar cambio (con límite superior)
            pattern.confidence = min(1.0, pattern.confidence + delta)
            
            # Registrar cambio
            change = pattern.confidence - old_confidence
            confidence_changes[pattern.id] = change
            self.stats['patterns_updated'] += 1
        
        # Actualizar estadísticas
        self.stats['total_positive_passes'] += 1
        self._update_avg_goodness('positive', goodness_score)
        
        # Crear episodio
        episode = FFEpisode(
            timestamp=time.time(),
            mode='positive',
            patterns_used=[p.id for p in successful_patterns],
            outcome='success',
            confidence_changes=confidence_changes,
            goodness_score=goodness_score
        )
        self.episodes.append(episode)
        
        print(f"[FF+] ✨ Positive Pass: {len(successful_patterns)} patrones reforzados")
        
        return confidence_changes
    
    def negative_pass(self, failed_patterns: List[MarketStoredPattern],
                     corrupted_data: Optional[List[Any]] = None) -> Dict[str, float]:
        """
        Q5: Negative Pass - Minimizar score de patrones fallidos.
        
        Análogo a FF negative pass con datos corruptos.
        
        Formalización:
          Para cada patrón fallido p:
            E(p) ← E(p) - δ⁻ × ff_learning_rate × negative_pass_multiplier
            goodness(p) = 1 - (score(p) / max_score)
        
        Args:
            failed_patterns: Lista de patrones que llevaron a fallo
            corrupted_data: Datos corruptos opcionales para negative pass
        
        Returns:
            Dict[str, float]: Cambios de confianza por patrón
        """
        confidence_changes = {}
        
        for pattern in failed_patterns:
            old_confidence = pattern.confidence
            
            # Calcular goodness inverso para datos fallidos
            goodness_inverse = 1.0 - (pattern.confidence / 1.0)
            
            # Actualizar E(pt) con multiplicador FF
            delta = (
                self.config.ff_learning_rate *
                self.config.negative_pass_multiplier *
                goodness_inverse
            )
            
            # Aplicar cambio (con límite inferior)
            pattern.confidence = max(0.1, pattern.confidence - delta)
            
            # Registrar cambio
            change = old_confidence - pattern.confidence  # Cambio positivo (reducción)
            confidence_changes[pattern.id] = -change  # Negativo indica reducción
            self.stats['patterns_updated'] += 1
        
        # Actualizar estadísticas
        self.stats['total_negative_passes'] += 1
        
        # Calcular goodness promedio para negative pass
        avg_goodness = np.mean([1.0 - p.confidence for p in failed_patterns])
        self._update_avg_goodness('negative', avg_goodness)
        
        # Crear episodio
        episode = FFEpisode(
            timestamp=time.time(),
            mode='negative',
            patterns_used=[p.id for p in failed_patterns],
            outcome='failure',
            confidence_changes=confidence_changes,
            goodness_score=avg_goodness
        )
        self.episodes.append(episode)
        
        print(f"[FF-] ⚠️ Negative Pass: {len(failed_patterns)} patrones penalizados")
        
        return confidence_changes
    
    # ========================================================================
    # Q6: FF COMO META-PATRÓN IMPORTABLE
    # ========================================================================
    
    def execute_ff_cycle(self, successful_patterns: List[MarketStoredPattern],
                        failed_patterns: List[MarketStoredPattern]) -> Dict[str, Any]:
        """
        Q6: Ejecutar ciclo completo Forward-Forward como meta-patrón.
        
        Este método es importado por Ψ cuando se detecta estancamiento.
        
        Flujo:
        1. Activar FF (si no está activo)
        2. Ejecutar positive pass con patrones exitosos
        3. Ejecutar negative pass con patrones fallidos
        4. Verificar convergencia
        5. Desactivar si converge o alcanza máximo iteraciones
        
        Args:
            successful_patterns: Patrones que llevaron a éxito
            failed_patterns: Patrones que llevaron a fallo
        
        Returns:
            Dict[str, Any]: Resultados del ciclo FF
        """
        # Activar si no está activo
        if not self.is_active:
            self.activate_ff()
        
        # Ejecutar pases
        positive_changes = self.positive_pass(successful_patterns)
        negative_changes = self.negative_pass(failed_patterns)
        
        # Incrementar iteración
        self.current_iteration += 1
        
        # Verificar convergencia
        total_change = (
            sum(abs(v) for v in positive_changes.values()) +
            sum(abs(v) for v in negative_changes.values())
        )
        
        converged = (
            total_change < self.config.min_confidence_change or
            self.current_iteration >= self.config.max_ff_iterations
        )
        
        if converged:
            self.deactivate_ff()
        
        # Retornar resultados
        return {
            'iteration': self.current_iteration,
            'positive_changes': positive_changes,
            'negative_changes': negative_changes,
            'total_change': total_change,
            'converged': converged,
            'is_active': self.is_active
        }
    
    # ========================================================================
    # UTILIDADES
    # ========================================================================
    
    def _update_avg_goodness(self, mode: str, goodness: float):
        """Actualizar promedio móvil de goodness."""
        if mode == 'positive':
            old_avg = self.stats['avg_goodness_positive']
            n = self.stats['total_positive_passes']
            self.stats['avg_goodness_positive'] = ((old_avg * (n-1)) + goodness) / n
        else:
            old_avg = self.stats['avg_goodness_negative']
            n = self.stats['total_negative_passes']
            self.stats['avg_goodness_negative'] = ((old_avg * (n-1)) + goodness) / n
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas de FF."""
        return {
            **self.stats,
            'is_active': self.is_active,
            'current_iteration': self.current_iteration,
            'stagnation_detected': self.stagnation_detected,
            'episodes_count': len(self.episodes)
        }
    
    def reset(self):
        """Reiniciar estado para nuevo ciclo."""
        self.is_active = False
        self.current_iteration = 0
        self.stagnation_detected = False


# ============================================================================
# INTEGRACIÓN CON TRADING BOT
# ============================================================================

def integrate_with_trading_bot(bot, ff_learner: ForwardForwardLearner,
                              backtracks: int, progress: int,
                              recent_trades: List[Dict[str, Any]],
                              successful_patterns: List[MarketStoredPattern],
                              failed_patterns: List[MarketStoredPattern]):
    """
    Integrar FF con TradingBot existente.
    
    Uso:
      1. Llamar en cada barra/episodio
      2. Si detecta estancamiento, activa FF automáticamente
      3. Ejecuta ciclo FF con patrones exitosos/fallidos
    
    Args:
        bot: TradingBot o TradingBotAutonomous
        ff_learner: Instancia de ForwardForwardLearner
        backtracks: Número de backtracks recientes
        progress: Progreso en ventana actual
        recent_trades: Lista de trades recientes
        successful_patterns: Patrones exitosos
        failed_patterns: Patrones fallidos
    
    Returns:
        Dict[str, Any]: Resultados del ciclo FF (vacío si no se activó)
    """
    # Q11: Verificar estancamiento
    if ff_learner.check_stagnation(backtracks, progress, recent_trades):
        # Q6: Ejecutar ciclo FF como meta-patrón
        results = ff_learner.execute_ff_cycle(
            successful_patterns=successful_patterns,
            failed_patterns=failed_patterns
        )
        
        # Actualizar meta-parámetros del bot si FF convergió
        if results.get('converged', False):
            # Ajustar thresholds basados en cambios de FF
            for pattern_id, change in results['positive_changes'].items():
                if change > 0.05:
                    # Patrón muy reforzado, reducir umbral de activación
                    pass  # Implementar ajuste fino si es necesario
        
        return results
    
    return {}


# ============================================================================
# TESTS
# ============================================================================

if __name__ == "__main__":
    print("="*70)
    print("TEST: Forward-Forward Learner - MSE v5.0.2-R (Q5, Q6, Q11)")
    print("="*70)
    
    # Crear pattern_db mock
    from src.python.market.market_pattern_database import MarketPatternDatabase, create_builtin_patterns
    
    pattern_db = MarketPatternDatabase()
    builtin = create_builtin_patterns()
    for p in builtin:
        pattern_db.stored_patterns.append(p)
    
    # Test 1: Crear FF learner
    print("\nTest 1: Crear ForwardForwardLearner")
    ff = ForwardForwardLearner(pattern_db)
    print(f"  Config: backtracks_threshold={ff.config.stagnation_backtracks_threshold}")
    print(f"  FF learning rate: {ff.config.ff_learning_rate}")
    print("  ✅ PASSED")
    
    # Test 2: Detección de estancamiento (Q11)
    print("\nTest 2: Detección de estancamiento (Q11)")
    
    # Caso NO estancamiento
    is_stagnant = ff.check_stagnation(
        backtracks=30,  # < 50 threshold
        progress=1,
        recent_trades=[{'pnl': 100}, {'pnl': 50}, {'pnl': -20}]
    )
    print(f"  Sin estancamiento (backtracks=30, progress=1): {is_stagnant}")
    assert is_stagnant == False
    
    # Caso SÍ estancamiento
    is_stagnant = ff.check_stagnation(
        backtracks=100,  # > 50 threshold
        progress=0,
        recent_trades=[{'pnl': -50}, {'pnl': -30}, {'pnl': -40}, {'pnl': -20}, {'pnl': -10}]
    )
    print(f"  Con estancamiento (backtracks=100, progress=0): {is_stagnant}")
    assert is_stagnant == True
    print("  ✅ PASSED")
    
    # Test 3: Positive Pass (Q5)
    print("\nTest 3: Positive Pass (Q5)")
    successful = [p for p in pattern_db.stored_patterns if p.pattern_type == 'range_buy_low']
    if successful:
        changes = ff.positive_pass(successful, goodness_score=0.9)
        print(f"  Patrones reforzados: {len(changes)}")
        for pid, change in changes.items():
            print(f"    {pid}: ΔE(pt) = +{change:.4f}")
        print("  ✅ PASSED")
    
    # Test 4: Negative Pass (Q5)
    print("\nTest 4: Negative Pass (Q5)")
    failed = [p for p in pattern_db.stored_patterns if p.pattern_type == 'range_sell_high']
    if failed:
        changes = ff.negative_pass(failed)
        print(f"  Patrones penalizados: {len(changes)}")
        for pid, change in changes.items():
            print(f"    {pid}: ΔE(pt) = {change:.4f}")
        print("  ✅ PASSED")
    
    # Test 5: Ciclo FF completo (Q6)
    print("\nTest 5: Ciclo FF completo (Q6)")
    ff.activate_ff()
    results = ff.execute_ff_cycle(
        successful_patterns=successful if successful else [],
        failed_patterns=failed if failed else []
    )
    print(f"  Iteración: {results['iteration']}")
    print(f"  Convergió: {results['converged']}")
    print(f"  Activo: {results['is_active']}")
    print(f"  Cambio total: {results['total_change']:.4f}")
    print("  ✅ PASSED")
    
    # Test 6: Estadísticas
    print("\nTest 6: Estadísticas de FF")
    stats = ff.get_stats()
    print(f"  Activaciones: {stats['total_activations']}")
    print(f"  Positive passes: {stats['total_positive_passes']}")
    print(f"  Negative passes: {stats['total_negative_passes']}")
    print(f"  Patrones actualizados: {stats['patterns_updated']}")
    print(f"  Goodness positive avg: {stats['avg_goodness_positive']:.3f}")
    print(f"  Goodness negative avg: {stats['avg_goodness_negative']:.3f}")
    print("  ✅ PASSED")
    
    print("\n" + "="*70)
    print("TESTS DE FORWARD-FORWARD PASSED")
    print("="*70)
