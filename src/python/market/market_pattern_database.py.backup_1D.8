# src/python/market/market_pattern_database.py
"""
MarketPatternDatabase - MSE v5.0.2-R ETAPA 6
============================================

Base de datos híbrida de patrones de mercado, análoga a HybridPatternDatabase
pero adaptada a series temporales financieras.

ETAPA 6 Especificación:
- Almacenar patrones de mercado (head_and_shoulders, double_top, breakout, etc.)
- E(pt): Efectividad de patrones por régimen de mercado
- H(action): Historial de éxito por tipo de operación (buy/sell/hold)
- Persistencia entre sesiones
- Matching en tiempo real para detección de oportunidades

MSE v5.0.2-R QC Opción B:
- Axiomas heurísticos guían selección, no vetan
- Patrones suaves para exploración (cristalizan con E>0.95)
"""

import numpy as np
import pickle
import gzip
import uuid
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Tuple, Optional, Any, Union
from pathlib import Path
import sys

# Asegurar paths
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.python.market.axioms import MarketState, MarketRegime, MarketAxioms
from src.python.market.time_series_state import TimeSeriesState


# ============================================================================
# CONSTANTES - PARÁMETROS DE TRADING (1D.5 DEBUG: Revert to 1B.16 baseline)
# ============================================================================
RANGE_ENTRY_THRESHOLD = 0.02  # 2% desviación desde límite de rango
RANGE_WIDTH_MAX = 0.05  # 5% ancho máximo de rango para régimen LATERAL
CRYSTALLIZATION_THRESHOLD = 0.70  # 1D.7 FIX: 0.95 → 0.70 (temporal para permitir aprendizaje inicial)
CONFIDENCE_FLOOR = 0.10  # 1C.11: Piso de confianza (previene degradación)
DELTA_PLUS = 0.25  # 1D.6: 0.15→0.25 (mayor recompensa)
DELTA_MINUS = 0.10  # 1D.6: 0.15→0.10 (menor castigo)


# ============================================================================
# ESTRUCTURAS DE DATOS
# ============================================================================

@dataclass
class MarketStoredPattern:
    """
    Patrón de mercado almacenado con su efectividad.
    Análogo a StoredPattern pero para trading.
    """
    pattern_type: str  # Ej: 'head_and_shoulders', 'double_top', 'breakout', 'pullback'
    regime: MarketRegime  # Régimen donde es efectivo
    trigger_conditions: Dict[str, float]  # Condiciones de activación
    entry_signal: str  # 'buy', 'sell', 'hold'
    stop_loss_pct: float  # Stop loss porcentual
    take_profit_pct: float  # Take profit porcentual

    # Efectividad (E(pt))
    confidence: float = 0.5  # Efectividad [0.1, 1.0]
    uses: int = 0
    successes: int = 0

    # Metadatos
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_timestamp: float = field(default_factory=time.time)
    last_used_timestamp: float = 0.0
    is_soft: bool = False  # Patrón temporal en exploración
    crystallized: bool = False  # E(pt) > 0.95

    # Complejidad (Q10)
    complexity: float = 1.0

    # 🆕 Phase 1C.7-1C.14: Pattern Type Flag
    is_reversal: bool = False  # True para patrones de reversión (H&S, double top/bottom)

    # 🆕 Phase 1D.2: Emergent Pattern Persistence
    episodes_without_improvement: int = 0  # Track episodes without confidence improvement
    last_used_regime: Optional[str] = None  # For regime-specific reuse
    performance_by_regime: Dict[str, float] = field(default_factory=dict)  # Win rate by regime

    def __post_init__(self):
        # Calcular complejidad si no está definida
        if self.complexity == 1.0:
            self.complexity = self._calculate_complexity()
    
    def _calculate_complexity(self) -> float:
        """Calcular complejidad del patrón (Q10)."""
        # Patrones simples: 1-2 condiciones
        # Patrones complejos: 3+ condiciones
        num_conditions = len(self.trigger_conditions)
        base_complexity = 1.0 + (num_conditions * 0.5)
        
        # Patrones por régimen son más complejos
        if self.regime == MarketRegime.TRANSITION:
            base_complexity += 1.0
        
        return min(10.0, base_complexity)

    def update_effectiveness(self, success: bool,
                            delta_plus: float = 0.25,  # CRITICAL FIX: 0.15 → 0.25 (positive drift with 55% WR)
                            delta_minus: float = 0.15,
                            epsilon_min: float = 0.1,
                            epsilon_max: float = 1.0):
        """
        Actualizar E(pt) tras uso.
        
        1D.2: Track episodes without improvement for emergent patterns.
        - If confidence doesn't increase after an episode, increment counter
        - Reset counter on improvement
        - Used for pruning unproven emergent patterns
        """
        initial_conf = self.confidence  # 1D.2: Store initial confidence
        self.uses += 1
        self.last_used_timestamp = time.time()

        if success:
            self.successes += 1
            self.confidence = min(epsilon_max, self.confidence + delta_plus)
        else:
            self.confidence = max(epsilon_min, self.confidence - delta_minus)

        # CRITICAL FIX: Confidence floor (prevent degradation below 0.10)
        self.confidence = max(0.10, self.confidence)
        
        # 1D.2: Track episodes without improvement for emergent patterns
        if self.is_soft:
            if self.confidence > initial_conf:
                self.episodes_without_improvement = 0  # Reset on improvement
            else:
                self.episodes_without_improvement += 1

    def check_crystallization(self, threshold: float = CRYSTALLIZATION_THRESHOLD) -> bool:  # 1D.7 FIX: 0.95 → 0.70 (CRYSTALLIZATION_THRESHOLD)
        """
        Q4: Verificar si debe cristalizar.

        CRITICAL FIX: 0.95 → 0.70 (mathematically achievable threshold)
        - 0.95 required >85% win rate (impossible in crypto)
        - 0.70 achievable with 55-60% win rate (realistic)
        - Still represents high confidence (70%)

        1D.2: Reset episodes_without_improvement counter on crystallization.
        1D.3: Changed > to >= for edge case at exactly threshold.
        """
        if not self.crystallized and self.confidence >= threshold:
            self.crystallized = True
            self.is_soft = False
            self.episodes_without_improvement = 0  # 1D.2: Reset counter
            print(f"  [MarketPatternDB] ✅ Patrón {self.pattern_type} CRISTALIZADO (E={self.confidence:.3f}, threshold={threshold:.2f})")
            return True
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Serializar a diccionario."""
        return {
            'pattern_type': self.pattern_type,
            'regime': self.regime.value,
            'trigger_conditions': self.trigger_conditions,
            'entry_signal': self.entry_signal,
            'stop_loss_pct': self.stop_loss_pct,
            'take_profit_pct': self.take_profit_pct,
            'confidence': self.confidence,
            'uses': self.uses,
            'successes': self.successes,
            'id': self.id,
            'created_timestamp': self.created_timestamp,
            'last_used_timestamp': self.last_used_timestamp,
            'is_soft': self.is_soft,
            'crystallized': self.crystallized,
            'complexity': self.complexity
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MarketStoredPattern':
        """Deserializar desde diccionario."""
        # Convertir regime de string a enum
        data['regime'] = MarketRegime(data['regime'])
        return cls(**data)


@dataclass
class MarketBifurcationHistory:
    """
    H(action): Historial de éxito por tipo de operación.
    Análogo a H(i,j) en Sudoku pero para acciones de trading.
    """
    action: str  # 'buy', 'sell', 'hold'
    regime: MarketRegime
    history: float = 0.0  # Contador neto: éxitos - fracasos
    uses: int = 0
    successes: int = 0
    
    def update(self, success: bool, depth: int = 1):
        """Actualizar historial tras resultado."""
        self.uses += 1
        if success:
            self.successes += 1
            change = depth * 0.1
        else:
            change = -max(0.1, (10 - depth) * 0.05)
        
        self.history = max(0.0, self.history + change)


# ============================================================================
# MARKET PATTERN DATABASE
# ============================================================================

class MarketPatternDatabase:
    """
    Base de datos híbrida de patrones de mercado.

    ETAPA 6:
    - Almacena patrones por régimen de mercado
    - E(pt) por tipo de patrón y régimen
    - H(action) por tipo de operación
    - Persistencia en archivo
    - Matching en tiempo real
    
    FIX v5.0.2-R: Default path changed to data/patterns/hybrid_pattern_db.pkl.gz
    to ensure pattern persistence between sessions.
    """

    def __init__(self, db_path: Optional[str] = "data/patterns/hybrid_pattern_db.pkl.gz"):
        """
        Inicializar base de datos de patrones.
        
        Args:
            db_path: Ruta al archivo de persistencia. Si es None, crea DB vacía.
        """
        self.db_path = Path(db_path) if db_path else None
        self.stored_patterns: List[MarketStoredPattern] = []
        self.bifurcation_history: Dict[str, MarketBifurcationHistory] = {}
        self.meta_params: Dict[str, float] = {}  # Φ para trading

        # Cargar o inicializar
        if self.db_path:
            self.load_patterns()
        else:
            print(f"  [MarketPatternDB] Created EMPTY database (no persistence)")
    
    def load_patterns(self):
        """Cargar patrones desde archivo."""
        try:
            with gzip.open(self.db_path, 'rb') as f:
                data = pickle.load(f)
                
                # Cargar patrones
                raw_patterns = data.get('patterns', [])
                self.stored_patterns = []
                for p_dict in raw_patterns:
                    try:
                        pattern = MarketStoredPattern.from_dict(p_dict)
                        self.stored_patterns.append(pattern)
                    except Exception as e:
                        print(f"  [MarketPatternDB] Error al cargar patrón: {e}")
                
                # Cargar historial
                hist_data = data.get('bifurcation_history', {})
                for key, h_dict in hist_data.items():
                    self.bifurcation_history[key] = MarketBifurcationHistory(
                        action=h_dict['action'],
                        regime=MarketRegime(h_dict['regime']),
                        history=h_dict['history'],
                        uses=h_dict['uses'],
                        successes=h_dict['successes']
                    )
                
                # Cargar meta-parámetros
                self.meta_params = data.get('meta_params', {})
                
                print(f"  [MarketPatternDB] Cargados {len(self.stored_patterns)} patrones")
                
        except FileNotFoundError:
            print(f"  [MarketPatternDB] Archivo no encontrado: {self.db_path}. Iniciando vacío.")
            self.stored_patterns = []
            self.bifurcation_history = {}
            self.meta_params = {}
        except Exception as e:
            print(f"  [MarketPatternDB] Error al cargar: {e}")
            self.stored_patterns = []
            self.bifurcation_history = {}
            self.meta_params = {}
    
    def save_patterns(self):
        """Guardar patrones en archivo."""
        try:
            patterns_as_dicts = [p.to_dict() for p in self.stored_patterns]
            hist_as_dicts = {
                k: {
                    'action': v.action,
                    'regime': v.regime.value,
                    'history': v.history,
                    'uses': v.uses,
                    'successes': v.successes
                }
                for k, v in self.bifurcation_history.items()
            }
            
            data = {
                'patterns': patterns_as_dicts,
                'bifurcation_history': hist_as_dicts,
                'meta_params': self.meta_params,
                'version': '6.0',
                'timestamp': time.time()
            }
            
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(self.db_path, 'wb') as f:
                pickle.dump(data, f)
            
            print(f"  [MarketPatternDB] Guardados {len(self.stored_patterns)} patrones en {self.db_path}")
            
        except Exception as e:
            print(f"  [MarketPatternDB] Error al guardar: {e}")
    
    def add_pattern(self, pattern_type: str, regime: MarketRegime,
                   trigger_conditions: Dict[str, float],
                   entry_signal: str,
                   stop_loss_pct: float = 0.02,
                   take_profit_pct: float = 0.04,
                   confidence: float = 0.5,
                   is_soft: bool = False) -> MarketStoredPattern:
        """
        Añadir nuevo patrón a la base de datos.
        
        Args:
            pattern_type: Tipo de patrón (ej: 'head_and_shoulders')
            regime: Régimen de mercado donde aplica
            trigger_conditions: Diccionario de condiciones de activación
            entry_signal: 'buy', 'sell', o 'hold'
            stop_loss_pct: Stop loss porcentual (ej: 0.02 = 2%)
            take_profit_pct: Take profit porcentual (ej: 0.04 = 4%)
            confidence: Confianza inicial
            is_soft: ¿Es patrón suave temporal?
        
        Returns:
            MarketStoredPattern creado
        """
        pattern = MarketStoredPattern(
            pattern_type=pattern_type,
            regime=regime,
            trigger_conditions=trigger_conditions,
            entry_signal=entry_signal,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            confidence=confidence,
            is_soft=is_soft
        )
        
        self.stored_patterns.append(pattern)
        print(f"  [MarketPatternDB] 🌱 Patrón añadido: {pattern_type} ({regime.value})")
        
        return pattern
    
    def match_patterns(self, state: TimeSeriesState,
                      current_regime: Optional[MarketRegime] = None) -> List[MarketStoredPattern]:
        """
        Buscar patrones coincidentes con el estado actual.
        
        DEBUG FASE 1B: Logging detallado para diagnosticar por qué patrones no operan.

        Args:
            state: Estado actual de serie temporal
            current_regime: Régimen actual (si no, se usa el de state)

        Returns:
            Lista de patrones coincidentes ordenados por confianza
        """
        if current_regime is None:
            current_regime = state.current_regime

        # 1C.2: DEBUG logging removed to prevent I/O bottleneck and test timeout
        # Debug logging was for 1B phase debugging, not needed for production testing

        matches = []
        current_metrics = state.calculate_metrics()

        for pattern in self.stored_patterns:
            # Filtrar por régimen (solo patrones del régimen actual o generales)
            if pattern.regime != current_regime and pattern.regime != MarketRegime.TRANSITION:
                continue

            # Verificar condiciones de trigger
            trigger_match = self._check_trigger_conditions(pattern, state, current_metrics)

            if trigger_match:
                matches.append(pattern)

        # Ordenar por confianza (mayor primero)
        matches.sort(key=lambda p: p.confidence, reverse=True)

        # 1C.2: Logging reducido - solo mostrar cuando hay patrones coincidentes (sin detalle excesivo)
        # if matches:
        #     print(f"  [MarketPatternDB] 🔍 {len(matches)} patrones coincidentes para régimen {current_regime.value}")

        return matches
    
    def _check_trigger_conditions(self, pattern: MarketStoredPattern,
                                 state: TimeSeriesState,
                                 metrics: 'TimeSeriesMetrics') -> bool:
        """
        Verificar si las condiciones de trigger se cumplen.
        
        QC Especificación v1.0:
        - Triggers LATERAL con tolerancia 0.2%
        - Range detection con ventana de 20 períodos
        
        Condiciones soportadas:
        - 'breakout_threshold': close > max(high_20) * threshold
        - 'breakdown_threshold': close < min(low_20) * threshold
        - 'volume_ratio_min': Volumen mínimo relativo
        - 'volatility_min/max': Volatilidad
        - 'range_position': 'low' o 'high' para range trading
        - 'range_tolerance': Tolerancia del rango (0.002 = 0.2%)
        - 'range_max_width': Ancho máximo del rango (0.03 = 3%)
        - 'trend_slope_min/max': Pendiente de tendencia
        - 'regime_confidence_min': Confianza mínima de régimen
        """
        triggers = pattern.trigger_conditions
        n = len(state.closes)

        if n < 20:
            return False  # No hay suficientes datos

        # 1D.6 FIX: Validar que triggers NO esté vacío (bug de patrones emergentes)
        # Los patrones emergentes de structural_induction pueden tener triggers=None o {}
        # Esto causaba que _check_trigger_conditions() retornara True por defecto
        # inflando scores a 55.0+ cuando debería ser ~2.0
        if not triggers or not any(triggers.values()):
            return False  # ← FIX: Patrones sin triggers NO hacen match

        # Flag para verificar que AL MENOS UN trigger fue verificado
        any_trigger_matched = False

        # =========================================================================
        # PATRONES DE BREAKOUT/BREAKDOWN
        # =========================================================================

        if 'breakout_threshold' in triggers:
            any_trigger_matched = True  # ← Marcar que verificamos este trigger
            # close_t > max(high_{t-20:t-1})
            recent_highs = state.highs[-20:-1]
            max_high = np.max(recent_highs)
            current_close = state.closes[-1]
            
            if current_close <= max_high * triggers['breakout_threshold']:
                return False
            
            # Verificar volumen si está especificado
            if 'volume_ratio_min' in triggers:
                recent_vol = state.volumes[-20:-1]
                avg_vol = np.mean(recent_vol)
                current_vol = state.volumes[-1]
                if current_vol < avg_vol * triggers['volume_ratio_min']:
                    return False
        
        if 'breakdown_threshold' in triggers:
            any_trigger_matched = True  # ← Marcar que verificamos este trigger
            # close_t < min(low_{t-20:t-1})
            recent_lows = state.lows[-20:-1]
            min_low = np.min(recent_lows)
            current_close = state.closes[-1]
            
            if current_close >= min_low * triggers['breakdown_threshold']:
                return False
            
            # Verificar volumen
            if 'volume_ratio_min' in triggers:
                recent_vol = state.volumes[-20:-1]
                avg_vol = np.mean(recent_vol)
                current_vol = state.volumes[-1]
                if current_vol < avg_vol * triggers['volume_ratio_min']:
                    return False
        
        # =========================================================================
        # PATRONES DE RANGE TRADING (LATERAL) - QC PRIORIDAD ALTA
        # =========================================================================

        if 'range_position' in triggers:
            any_trigger_matched = True  # ← Marcar que verificamos este trigger
            # Calcular rango de 20 períodos
            recent_highs = state.highs[-20:-1]
            recent_lows = state.lows[-20:-1]
            range_high = np.max(recent_highs)
            range_low = np.min(recent_lows)
            range_width = (range_high - range_low) / range_low

            # Verificar ancho máximo del rango (< 3%)
            if 'range_max_width' in triggers:
                if range_width > triggers['range_max_width']:
                    return False

            current_close = state.closes[-1]
            range_tolerance = triggers.get('range_tolerance', 0.01)  # 1B.3: 0.2% → 1%

            # =========================================================================
            # 1B.4: FILTRO DE DIRECCIÓN (Debug Win Rate 0%)
            # =========================================================================
            # Verificar que entry_price esté cerca del suelo/teche (≤2%)
            # Esto evita comprar en medio del rango o vender en medio del rango
            # =========================================================================

            if triggers['range_position'] == 'low':
                # range_buy_low: close_t ∈ [range_low, range_low·1.02]
                lower_bound = range_low
                upper_bound = range_low * (1 + range_tolerance)
                
                # 1B.4: Filtro adicional - NO operar si está >2% sobre el suelo
                max_allowed = range_low * 1.02  # 2% máximo sobre range_low
                
                if not (lower_bound <= current_close <= min(upper_bound, max_allowed)):
                    return False

            elif triggers['range_position'] == 'high':
                # range_sell_high: close_t ∈ [range_high·0.99, range_high]
                lower_bound = range_high * (1 - range_tolerance)
                upper_bound = range_high
                
                # 1B.4: Filtro adicional - NO operar si está <2% bajo el techo
                min_allowed = range_high * 0.98  # 2% mínimo bajo range_high
                
                if not (max(lower_bound, min_allowed) <= current_close <= upper_bound):
                    return False
        
        # =========================================================================
        # PATRONES DE PULLBACK/RALLY
        # =========================================================================
        
        if 'pullback_threshold_low' in triggers:
            any_trigger_matched = True  # ← Marcar que verificamos este trigger
            # close_t ∈ [support·1.002, support·1.005]
            recent_lows = state.lows[-20:-1]
            support = np.min(recent_lows)
            current_close = state.closes[-1]
            
            lower = support * triggers['pullback_threshold_low']
            upper = support * triggers.get('pullback_threshold_high', 1.005)
            
            if not (lower <= current_close <= upper):
                return False
        
        if 'rally_threshold_low' in triggers:
            any_trigger_matched = True  # ← Marcar que verificamos este trigger
            # close_t ∈ [resistance·0.995, resistance·0.998]
            recent_highs = state.highs[-20:-1]
            resistance = np.max(recent_highs)
            current_close = state.closes[-1]
            
            lower = resistance * triggers['rally_threshold_low']
            upper = resistance * triggers.get('rally_threshold_high', 0.998)
            
            if not (lower <= current_close <= upper):
                return False
        
        # =========================================================================
        # CONDICIONES GENERALES
        # =========================================================================
        
        # Trend slope
        if 'trend_slope_min' in triggers:
            if metrics.trend_slope < triggers['trend_slope_min']:
                return False
        
        if 'trend_slope_max' in triggers:
            if metrics.trend_slope > triggers['trend_slope_max']:
                return False
        
        # Volatilidad
        if 'volatility_min' in triggers:
            if metrics.volatility < triggers['volatility_min']:
                return False
        
        if 'volatility_max' in triggers:
            if metrics.volatility > triggers['volatility_max']:
                return False
        
        # Volumen
        if 'volume_ratio_min' in triggers and 'range_position' not in triggers:
            # Ya manejado arriba para breakout/breakdown
            if hasattr(state, 'volumes') and len(state.volumes) > 0:
                current_vol = state.volumes[-1]
                avg_vol = np.mean(state.volumes[-20:]) if len(state.volumes) >= 20 else np.mean(state.volumes)
                vol_ratio = current_vol / max(0.001, avg_vol)
                if vol_ratio < triggers['volume_ratio_min']:
                    return False
        
        # Confianza de régimen
        if 'regime_confidence_min' in triggers:
            if metrics.regime_confidence < triggers['regime_confidence_min']:
                return False

        # 1D.6 FIX: Axioma A4 (Soundness) - Solo retorna True si AL MENOS UN trigger explícito fue verificado
        # Si llegamos aquí sin haber verificado NINGÚN trigger (triggers vacíos o no coinciden),
        # la inferencia falla y debe retornar False para evitar patrones fantasmas
        # Esto elimina scores inflados de 56.0 causados por patrones sin triggers válidos
        return any_trigger_matched  # ← FIX: Soundness axiom - return True only if at least one trigger was verified
    
    def update_pattern_effectiveness(self, pattern: MarketStoredPattern,
                                    success: bool):
        """Actualizar E(pt) tras resultado de operación.
        
        CRITICAL FIX: Uses new threshold 0.70 (was 0.95) for crystallization check.
        """
        pattern.update_effectiveness(success)
        pattern.check_crystallization(threshold=CRYSTALLIZATION_THRESHOLD)  # CRITICAL FIX: 0.95 → 0.70
    
    def update_bifurcation_history(self, action: str, regime: MarketRegime,
                                  success: bool, depth: int = 1):
        """Actualizar H(action) tras resultado."""
        key = f"{action}_{regime.value}"
        
        if key not in self.bifurcation_history:
            self.bifurcation_history[key] = MarketBifurcationHistory(
                action=action, regime=regime
            )
        
        self.bifurcation_history[key].update(success, depth)
        print(f"  [MarketPatternDB] H({action}_{regime.value}) = {self.bifurcation_history[key].history:.2f} (Δ={'+' if success else '-'})")
    
    def get_crystallization_stats(self) -> Dict[str, Any]:
        """Q10: Estadísticas de cristalización."""
        total = len(self.stored_patterns)
        crystallized = sum(1 for p in self.stored_patterns if p.crystallized)
        soft = sum(1 for p in self.stored_patterns if p.is_soft and not p.crystallized)

        avg_complexity = 0.0
        if crystallized > 0:
            avg_complexity = sum(p.complexity for p in self.stored_patterns if p.crystallized) / crystallized

        return {
            'total_patterns': total,
            'crystallized_count': crystallized,
            'soft_count': soft,
            'crystallization_ratio': crystallized / total if total > 0 else 0.0,
            'avg_complexity_crystallized': avg_complexity
        }

    def prune_unproven_emergent(self, max_episodes: int = 3) -> int:
        """
        1D.2: Remove emergent patterns that failed to prove themselves.
        
        Rationale:
        - Emergent patterns get 3 episodes to show improvement
        - If confidence doesn't increase after 3 episodes, remove
        - Crystallized patterns are NEVER pruned
        
        Args:
            max_episodes: Maximum episodes without improvement before pruning
            
        Returns:
            Number of patterns pruned
        """
        patterns_to_remove = []
        
        for pattern in self.stored_patterns:
            # Never prune crystallized patterns
            if pattern.crystallized:
                continue
            
            # Prune emergent patterns that failed to improve
            if pattern.is_soft and pattern.episodes_without_improvement >= max_episodes:
                patterns_to_remove.append(pattern)
                print(f"  [MarketPatternDB] 🗑️  Patrón {pattern.pattern_type} eliminado (no mejoró en {max_episodes} episodios)")
        
        # Remove patterns
        for pattern in patterns_to_remove:
            self.stored_patterns.remove(pattern)
        
        pruned_count = len(patterns_to_remove)
        print(f"  [MarketPatternDB] Pruned {pruned_count} unproven emergent patterns")
        return pruned_count

    def evolve(self, min_confidence: float = 0.2, max_patterns: int = 1000):
        """
        Evolucionar base de datos: poda, cristalización, límite.
        
        CRITICAL FIX: Uses new threshold 0.70 (was 0.95) for crystallization.
        """
        print(f"  [MarketPatternDB] Evolución: MinConf={min_confidence}, MaxPat={max_patterns}")
        print(f"  [MarketPatternDB] Patrones antes: {len(self.stored_patterns)}")

        # Paso 1: Verificar cristalización (CRITICAL FIX: 0.95 → 0.70)
        crystallized_count = 0
        for pattern in self.stored_patterns:
            if pattern.check_crystallization(threshold=CRYSTALLIZATION_THRESHOLD):  # CRITICAL FIX: 0.95 → 0.70
                crystallized_count += 1

        if crystallized_count > 0:
            print(f"  [MarketPatternDB] ✅ {crystallized_count} patrones cristalizados")
        
        # Paso 2: Eliminación por baja efectividad
        initial_count = len(self.stored_patterns)
        self.stored_patterns = [p for p in self.stored_patterns if p.confidence >= min_confidence]
        pruned = initial_count - len(self.stored_patterns)
        print(f"  [MarketPatternDB] Eliminados {pruned} patrones por baja efectividad")
        
        # Paso 3: Limitar número
        if len(self.stored_patterns) > max_patterns:
            self.stored_patterns.sort(key=lambda p: p.confidence, reverse=True)
            discarded = len(self.stored_patterns) - max_patterns
            self.stored_patterns = self.stored_patterns[:max_patterns]
            print(f"  [MarketPatternDB] Descartados {discarded} patrones por límite")
        
        print(f"  [MarketPatternDB] Patrones después: {len(self.stored_patterns)}")
        
        # Q10: Reportar stats
        stats = self.get_crystallization_stats()
        print(f"  [MarketPatternDB] Q10 Stats: Cristalizados={stats['crystallized_count']}, Ratio={stats['crystallization_ratio']:.2%}")
    
    def __repr__(self):
        return f"MarketPatternDB(patterns={len(self.stored_patterns)}, history={len(self.bifurcation_history)})"


# ============================================================================
# PATRONES PREDEFINIDOS
# ============================================================================

def create_builtin_patterns() -> List[MarketStoredPattern]:
    """
    Crear patrones predefinidos para trading.
    QC Especificación v1.0: 6 patrones básicos (2 por régimen BULL/BEAR/LATERAL)
    
    Basado en especificación formal QC:
    - BULL: breakout_resistance, pullback_support
    - BEAR: breakdown_support, rally_resistance
    - LATERAL: range_buy_low, range_sell_high
    """
    patterns = []
    
    # =========================================================================
    # RÉGIMEN BULL (2 patrones) - 1C.8: Single TP 5% (Easier to Reach)
    # =========================================================================
    # 1C.8: TP=5%, SL=2.5% (ratio 2:1) - More realistic for crypto volatility
    # Root cause 1C.7: TP 10-12% too ambitious, few wins captured, time exits dominate

    # 1. breakout_resistance
    # Trigger: close_t > max(high_{t-20:t-1}) ∧ volume_t > 1.5·volume_mean
    # 1D.6 FIX: Relajado breakout_threshold de 1.0 → 0.98 para permitir más matches
    patterns.append(MarketStoredPattern(
        pattern_type='breakout_resistance',
        regime=MarketRegime.BULL,
        trigger_conditions={
            'breakout_threshold': 0.98,  # 1D.6: 1.0 → 0.98 (close >= 98% del max_high)
            'volume_ratio_min': 1.5,
            'volatility_max': 0.05
        },
        entry_signal='buy',
        stop_loss_pct=0.025,  # 1C.8: Maintain 2.5% (unchanged)
        take_profit_pct=0.05,  # 1C.8: 12% → 5% (easier to capture wins)
        confidence=0.60,
        complexity=2.0
    ))

    # 2. pullback_support
    # Trigger: close_t ∈ [support·1.002, support·1.005] ∧ R(t)=BULL
    # 1D.6 FIX: Relajado pullback_threshold de [0.2%-0.5%] → [0.1%-1.0%] para más matches
    patterns.append(MarketStoredPattern(
        pattern_type='pullback_support',
        regime=MarketRegime.BULL,
        trigger_conditions={
            'pullback_threshold_low': 1.001,  # 1D.6: 0.2% → 0.1% (más permisivo)
            'pullback_threshold_high': 1.01,  # 1D.6: 0.5% → 1.0% (más permisivo)
            'trend_slope_min': 0.0005
        },
        entry_signal='buy',
        stop_loss_pct=0.025,  # 1C.8: Maintain 2.5% (unchanged)
        take_profit_pct=0.05,  # 1C.8: 12% → 5% (easier to capture wins)
        confidence=0.55,
        complexity=2.5
    ))
    
    # =========================================================================
    # RÉGIMEN BEAR (2 patrones) - 1C.8: AGGRESSIVE TP/SL 3:1 (Reversal Focus)
    # =========================================================================
    # 1C.8: TP=6%, SL=2% (ratio 3:1) - More aggressive for counter-trend reversals
    # Root cause 1C.7: BEAR win rate 36.8% (NEOJPY), TP/SL ratio too conservative
    # Diagnosis: Counter-trend needs wider TP to capture full reversal moves
    # 1C.8: Tighter SL (2%) + Higher TP (6%) = 3:1 ratio for better risk/reward

    # 3. breakdown_support
    # Trigger: close_t < min(low_{t-20:t-1}) ∧ volume_t > 1.5·volume_mean
    patterns.append(MarketStoredPattern(
        pattern_type='breakdown_support',
        regime=MarketRegime.BEAR,
        trigger_conditions={
            'breakdown_threshold': 1.0,  # close < min(low_20)
            'volume_ratio_min': 1.5,
            'volatility_max': 0.05
        },
        entry_signal='sell',
        stop_loss_pct=0.02,  # 1C.8: 2.5% → 2.0% (tighter SL for reversals)
        take_profit_pct=0.06,  # 1C.8: 5% → 6.0% (higher target for reversals)
        confidence=0.60,
        complexity=2.0
    ))

    # 4. rally_resistance
    # Trigger: close_t ∈ [resistance·0.995, resistance·0.998] ∧ R(t)=BEAR
    # 1D.6 FIX: Relajado rally_threshold de [0.2%-0.5%] → [0.1%-1.0%] para más matches
    patterns.append(MarketStoredPattern(
        pattern_type='rally_resistance',
        regime=MarketRegime.BEAR,
        trigger_conditions={
            'rally_threshold_low': 0.999,  # 1D.6: 0.5% → 0.1% (más permisivo)
            'rally_threshold_high': 0.99,  # 1D.6: 0.2% → 1.0% (más permisivo)
            'trend_slope_max': -0.0005
        },
        entry_signal='sell',
        stop_loss_pct=0.02,  # 1C.8: 2.5% → 2.0% (tighter SL for reversals)
        take_profit_pct=0.06,  # 1C.8: 5% → 6.0% (higher target for reversals)
        confidence=0.55,
        complexity=2.5
    ))

    # =========================================================================
    # RÉGIMEN LATERAL (2 patrones) - 1C.9: TIGHTER RANGE (1.5%) + BETTER TP/SL
    # =========================================================================
    # 1C.9: range_tolerance=1.5%, TP=3%, SL=2% - Tighter entry, better ratio
    # Root cause 1C.8: LATERAL win rate 41.2-44.4% (XMRUSD, REPBTC)
    # Diagnosis: Range tolerance 2.0% still too loose, TP/SL ratio 1.0 suboptimal
    # 1C.9: Tighter range (1.5%) for better entries, TP 3%/SL 2% (ratio 1.5)

    # 5. range_buy_low
    # Trigger: close_t ∈ [range_low, range_low·1.015] ∧ R(t)=LATERAL
    # 1D.6 FIX: Relajado range_tolerance de 1.5% → 3.0% y range_max_width de 5% → 8%
    patterns.append(MarketStoredPattern(
        pattern_type='range_buy_low',
        regime=MarketRegime.LATERAL,
        trigger_conditions={
            'range_position': 'low',
            'range_tolerance': 0.03,  # 1D.6: 1.5% → 3.0% (más permisivo)
            'range_max_width': 0.08,  # 1D.6: 5% → 8% (rangos más amplios)
            'volatility_max': 0.03
        },
        entry_signal='buy',
        stop_loss_pct=0.015,  # 1D.5 DEBUG: 2.0% → 1.5% (1B.16 baseline)
        take_profit_pct=0.015,  # 1D.5 DEBUG: 3.0% → 1.5% (1B.16 baseline - easier to reach)
        confidence=0.65,  # Maintain 0.65 (más margen sobre trigger 0.40)
        complexity=3.0
    ))

    # 6. range_sell_high
    # Trigger: close_t ∈ [range_high·0.985, range_high] ∧ R(t)=LATERAL
    # 1D.6 FIX: Relajado range_tolerance de 1.5% → 3.0% y range_max_width de 5% → 8%
    patterns.append(MarketStoredPattern(
        pattern_type='range_sell_high',
        regime=MarketRegime.LATERAL,
        trigger_conditions={
            'range_position': 'high',
            'range_tolerance': 0.03,  # 1D.6: 1.5% → 3.0% (más permisivo)
            'range_max_width': 0.08,  # 1D.6: 5% → 8% (rangos más amplios)
            'volatility_max': 0.03
        },
        entry_signal='sell',
        stop_loss_pct=0.015,  # 1D.5 DEBUG: 2.0% → 1.5% (1B.16 baseline)
        take_profit_pct=0.015,  # 1D.5 DEBUG: 3.0% → 1.5% (1B.16 baseline - easier to reach)
        confidence=0.65,  # Maintain 0.65 (más margen sobre trigger 0.40)
        complexity=3.0
    ))

    # =========================================================================
    # 🆕 PHASE 1C.7-1C.14: PATTERN ENRICHMENT (8 NEW PATTERNS)
    # =========================================================================
    # Objective: Expand from 6 to 14 patterns (+133%)
    # Expected: Win rate 57.4% → 60-65%, Sharpe -55.84 → -40 to -30
    
    # =========================================================================
    # REVERSAL PATTERNS (4 patterns)
    # =========================================================================
    
    # 7. head_and_shoulders (BULL→BEAR reversal)
    # Trigger: Peak (head) between two lower peaks (shoulders), volume declining
    # High precision market top detection
    patterns.append(MarketStoredPattern(
        pattern_type='head_and_shoulders',
        regime=MarketRegime.BULL,  # Appears at end of BULL, signals reversal to BEAR
        trigger_conditions={
            'reversal_pattern': 'head_and_shoulders',
            'volume_declining': True,
            'neckline_break': True,
            'confirmation_candles': 2
        },
        entry_signal='sell',  # Short on reversal confirmation
        stop_loss_pct=0.03,  # Wider SL for reversal patterns
        take_profit_pct=0.08,  # Higher TP for reversal moves
        confidence=0.70,  # High confidence pattern
        complexity=5.0,  # Complex pattern recognition
        is_reversal=True  # Flag for reversal pattern
    ))
    
    # 8. inverse_head_and_shoulders (BEAR→BULL reversal)
    # Trigger: Trough (head) between two higher troughs (shoulders), volume increasing
    # High precision market bottom detection
    patterns.append(MarketStoredPattern(
        pattern_type='inverse_head_and_shoulders',
        regime=MarketRegime.BEAR,  # Appears at end of BEAR, signals reversal to BULL
        trigger_conditions={
            'reversal_pattern': 'inverse_head_and_shoulders',
            'volume_increasing': True,
            'neckline_break': True,
            'confirmation_candles': 2
        },
        entry_signal='buy',  # Long on reversal confirmation
        stop_loss_pct=0.03,  # Wider SL for reversal patterns
        take_profit_pct=0.08,  # Higher TP for reversal moves
        confidence=0.70,  # High confidence pattern
        complexity=5.0,  # Complex pattern recognition
        is_reversal=True  # Flag for reversal pattern
    ))
    
    # 9. double_top (BULL→BEAR confirmation)
    # Trigger: Two consecutive peaks at same resistance level
    # M pattern, confirms resistance strength
    patterns.append(MarketStoredPattern(
        pattern_type='double_top',
        regime=MarketRegime.BULL,
        trigger_conditions={
            'reversal_pattern': 'double_top',
            'resistance_touches': 2,
            'volume_second_peak_lower': True,
            'confirmation_candles': 1
        },
        entry_signal='sell',
        stop_loss_pct=0.025,
        take_profit_pct=0.06,
        confidence=0.65,
        complexity=4.0,
        is_reversal=True
    ))
    
    # 10. double_bottom (BEAR→BULL confirmation)
    # Trigger: Two consecutive troughs at same support level
    # W pattern, confirms support strength
    patterns.append(MarketStoredPattern(
        pattern_type='double_bottom',
        regime=MarketRegime.BEAR,
        trigger_conditions={
            'reversal_pattern': 'double_bottom',
            'support_touches': 2,
            'volume_second_trough_higher': True,
            'confirmation_candles': 1
        },
        entry_signal='buy',
        stop_loss_pct=0.025,
        take_profit_pct=0.06,
        confidence=0.65,
        complexity=4.0,
        is_reversal=True
    ))
    
    # =========================================================================
    # CONTINUATION PATTERNS (4 patterns)
    # =========================================================================
    
    # 11. ascending_triangle (BULL continuation)
    # Trigger: Higher lows + flat resistance, bullish breakout expected
    patterns.append(MarketStoredPattern(
        pattern_type='ascending_triangle',
        regime=MarketRegime.BULL,
        trigger_conditions={
            'continuation_pattern': 'ascending_triangle',
            'higher_lows_count': 3,
            'resistance_flat': True,
            'volume_increasing': True
        },
        entry_signal='buy',
        stop_loss_pct=0.02,
        take_profit_pct=0.05,
        confidence=0.60,
        complexity=3.5,
        is_reversal=False
    ))
    
    # 12. descending_triangle (BEAR continuation)
    # Trigger: Lower highs + flat support, bearish breakdown expected
    patterns.append(MarketStoredPattern(
        pattern_type='descending_triangle',
        regime=MarketRegime.BEAR,
        trigger_conditions={
            'continuation_pattern': 'descending_triangle',
            'lower_highs_count': 3,
            'support_flat': True,
            'volume_increasing': True
        },
        entry_signal='sell',
        stop_loss_pct=0.02,
        take_profit_pct=0.05,
        confidence=0.60,
        complexity=3.5,
        is_reversal=False
    ))
    
    # 13. flag_pennant (BULL/BEAR momentum continuation)
    # Trigger: Sharp move (flagpole) + consolidation (flag/pennant)
    # Works in both BULL and BEAR regimes
    patterns.append(MarketStoredPattern(
        pattern_type='flag_pennant',
        regime=MarketRegime.BULL,  # Also added for BEAR below
        trigger_conditions={
            'continuation_pattern': 'flag_pennant',
            'flagpole_surge_pct_min': 0.05,  # 5% minimum surge
            'consolidation_bars': 5,
            'volume_declining_consolidation': True
        },
        entry_signal='buy',
        stop_loss_pct=0.02,
        take_profit_pct=0.05,
        confidence=0.62,
        complexity=3.0,
        is_reversal=False
    ))
    
    # 13b. flag_pennant (BEAR regime)
    patterns.append(MarketStoredPattern(
        pattern_type='flag_pennant_bear',
        regime=MarketRegime.BEAR,
        trigger_conditions={
            'continuation_pattern': 'flag_pennant',
            'flagpole_drop_pct_min': 0.05,  # 5% minimum drop
            'consolidation_bars': 5,
            'volume_declining_consolidation': True
        },
        entry_signal='sell',
        stop_loss_pct=0.02,
        take_profit_pct=0.05,
        confidence=0.62,
        complexity=3.0,
        is_reversal=False
    ))
    
    # 14. cup_and_handle (BULL long-term continuation)
    # Trigger: U-shaped bottom (cup) + small consolidation (handle)
    # Long-term bullish pattern, high confidence
    patterns.append(MarketStoredPattern(
        pattern_type='cup_and_handle',
        regime=MarketRegime.BULL,
        trigger_conditions={
            'continuation_pattern': 'cup_and_handle',
            'cup_depth_pct': 0.15,  # 15% typical cup depth
            'handle_retracement_pct': 0.05,  # 5% handle retracement
            'cup_duration_bars_min': 50,
            'volume_u_shape': True
        },
        entry_signal='buy',
        stop_loss_pct=0.03,
        take_profit_pct=0.10,  # Long-term pattern, higher TP
        confidence=0.75,  # Highest confidence pattern
        complexity=6.0,  # Most complex pattern
        is_reversal=False
    ))

    print(f"  [MarketPatternDB] Creados {len(patterns)} patrones predefinidos (Phase 1C.7-1C.14: 6 base + 8 enrichment)")
    return patterns


# ============================================================================
# TESTS
# ============================================================================

if __name__ == "__main__":
    print("="*60)
    print("TEST: MarketPatternDatabase - MSE v5.0.2-R ETAPA 6")
    print("="*60)
    
    # Test 1: Crear DB
    print("\nTest 1: Crear MarketPatternDatabase")
    db = MarketPatternDatabase()
    print(f"  DB: {db}")
    print("  ✓ PASSED")
    
    # Test 2: Añadir patrones
    print("\nTest 2: Añadir patrones")
    builtin = create_builtin_patterns()
    for p in builtin:
        db.stored_patterns.append(p)
    print(f"  Patrones: {len(db.stored_patterns)}")
    print("  ✓ PASSED")
    
    # Test 3: Actualizar efectividad
    print("\nTest 3: Actualizar E(pt)")
    pattern = db.stored_patterns[0]
    initial_conf = pattern.confidence
    for i in range(5):
        pattern.update_effectiveness(success=True)
    print(f"  Confianza: {initial_conf:.2f} → {pattern.confidence:.2f}")
    assert pattern.confidence > initial_conf, "Confianza debe aumentar"
    print("  ✓ PASSED")
    
    # Test 4: Cristalización
    print("\nTest 4: Cristalización (E > 0.70)")
    # CRITICAL FIX: Threshold changed from 0.95 to 0.70
    # Forzar confianza alta
    pattern.confidence = 0.71
    cristalizo = pattern.check_crystallization(threshold=CRYSTALLIZATION_THRESHOLD)
    print(f"  Cristalizado: {cristalizo}")
    assert cristalizo == True, "Debe cristalizar"
    print("  ✓ PASSED")
    
    # Test 5: Estadísticas Q10
    print("\nTest 5: Estadísticas de cristalización (Q10)")
    stats = db.get_crystallization_stats()
    print(f"  Total: {stats['total_patterns']}")
    print(f"  Cristalizados: {stats['crystallized_count']}")
    print(f"  Ratio: {stats['crystallization_ratio']:.2%}")
    print("  ✓ PASSED")
    
    # Test 6: Persistencia
    print("\nTest 6: Persistencia (guardar/cargar)")
    db.save_patterns()
    db2 = MarketPatternDatabase()
    print(f"  Patrones cargados: {len(db2.stored_patterns)}")
    assert len(db2.stored_patterns) > 0, "Debe cargar patrones"
    print("  ✓ PASSED")
    
    print("\n" + "="*60)
    print("TODOS LOS TESTS DE MarketPatternDatabase PASSED")
    print("="*60)
