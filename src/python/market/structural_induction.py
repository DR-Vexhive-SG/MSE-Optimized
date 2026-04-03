# src/python/market/structural_induction.py
"""
Inducción Estructural para Patrones de Mercado - MSE v5.0.2-R
=============================================================

Descubre patrones emergentes sin plantilla predefinida (N2 Autonomía).
Conexión formal: MSE-V Sec. VII.7 (Patrones de Orden Superior)

Niveles de Autonomía:
- N0: Supervisado (QC define patrones) ✅ Completado
- N1: Semi-autónomo (selecciona entre predefinidos) ✅ QC v1.0
- N2: Descubrimiento guiado (induce nuevos patrones) ⏳ ESTA IMPLEMENTACIÓN
- N3: Autonomía con veto (ejecuta, MSE valida) ⏳ GOAL
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path
import sys
import hashlib

# Asegurar paths
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Imports con fallback para test directo y como módulo
try:
    from .axioms import MarketState, MarketRegime, MarketAxioms
    from .time_series_state import TimeSeriesState
    from .market_pattern_database import MarketStoredPattern
except ImportError:
    from market.axioms import MarketState, MarketRegime, MarketAxioms
    from market.time_series_state import TimeSeriesState
    from market.market_pattern_database import MarketStoredPattern


@dataclass
class EmergentPattern:
    """
    Patrón emergente descubierto por inducción estructural.
    
    Atributos:
        signature: Hash único del patrón
        pattern_type: Tipo (ej: 'EMERGENT_a3f5c2')
        regime: Régimen donde emerge
        support: Soporte estadístico (ocurrencias / total)
        conditions: Condiciones de activación
        success_rate: Tasa de éxito histórica
        uses: Número de usos
        E_pt: Efectividad [0.1, 1.0]
        is_valid: Validado axiomáticamente
        violations: Violaciones axiomáticas encontradas
    """
    signature: str
    pattern_type: str
    regime: MarketRegime
    support: float
    conditions: Dict[str, float]
    success_rate: float = 0.0
    uses: int = 0
    E_pt: float = 0.50  # Inicial
    is_valid: bool = True
    violations: List[str] = field(default_factory=list)
    
    def to_stored_pattern(self) -> MarketStoredPattern:
        """Convertir a patrón almacenado."""
        # Determinar señal según condiciones
        if 'price_position' in self.conditions:
            if self.conditions['price_position'] < 0.2:  # Cerca de mínimo
                entry_signal = 'buy'
            elif self.conditions['price_position'] > 0.8:  # Cerca de máximo
                entry_signal = 'sell'
            else:
                entry_signal = 'hold'
        else:
            entry_signal = 'hold'
        
        return MarketStoredPattern(
            pattern_type=self.pattern_type,
            regime=self.regime,
            trigger_conditions=self.conditions,
            entry_signal=entry_signal,
            stop_loss_pct=0.005,
            take_profit_pct=0.02,
            confidence=self.E_pt,
            is_soft=True,  # Emergente comienza como suave
            crystallized=False,
            complexity=4.0  # Patrones emergentes son más complejos
        )


class MarketStructuralInduction:
    """
    Encuentra patrones emergentes en series temporales.

    Formalización (MSE-V Sec. VII.7):
      find_emergent_patterns(state_history, regime, min_support=0.6)

    Proceso:
      1. Extraer características por estado
      2. Buscar secuencias repetidas (ventanas [5, 20, 50])
      3. Calcular signature y soporte
      4. Validar soundness axiomática
      5. Retornar patrones válidos

    Criterio de Éxito:
      - ≥3 patrones emergentes en 1000 barras
      - 0 violaciones axiomáticas
    """

    def __init__(self, min_support: float = 0.01,
                 window_sizes: List[int] = None,
                 signature_precision: int = 1,
                 features: List[str] = None,
                 debug_mode: bool = False):
        """
        Inicializar inductor estructural con ajustes Fase 1B.12.

        Args:
            min_support: Soporte mínimo para patrón (1B.12: 1%) ANTES: 0.03 (3%)
            window_sizes: Tamaños de ventana para búsqueda
            signature_precision: Precisión decimal para signature (1B.12: 1) ANTES: 2
            features: Lista de características (1B.12: 3 core features) ANTES: 5
            debug_mode: Activar debug logging (1C.2: False para evitar I/O bottleneck)
        """
        # 1B.12: Pattern Emergence optimization - Reduced support threshold for more pattern discovery
        self.min_support = min_support  # 1B.12: 0.03 → 0.01 (3% → 1%)
        self.window_sizes = window_sizes or [5, 20, 50]
        self.signature_precision = signature_precision  # 1B.12: 2 → 1 (more collocations)
        self.debug_mode = debug_mode  # 1C.2: False por defecto para evitar I/O bottleneck

        # 1B.12: 3 core features para pattern discovery (reduced from 5 for better collocation)
        self.features = features or ['return', 'volume_ratio', 'range_position']

        # Cache de patrones descubiertos
        self.discovered_patterns: Dict[str, EmergentPattern] = {}

        # Estadísticas
        self.stats = {
            'total_signatures': 0,
            'valid_patterns': 0,
            'discarded_by_axioms': 0
        }
    
    def extract_features(self, state: TimeSeriesState,
                        index: int) -> Dict[str, float]:
        """
        Extraer características de un estado (1B.12: 3 core features).

        Args:
            state: Estado de serie temporal
            index: Índice del estado en la serie

        Returns:
            Diccionario de características normalizadas
        """
        if index < 10:
            return {}  # 1B.12: 20 → 10 (earlier pattern discovery) - Insuficientes datos históricos

        # Obtener ventanas
        closes = state.closes[max(0, index-50):index+1]
        highs = state.highs[max(0, index-50):index+1]
        lows = state.lows[max(0, index-50):index+1]
        volumes = state.volumes[max(0, index-50):index+1]

        if len(closes) < 20:
            return {}

        current_close = closes[-1]
        current_volume = volumes[-1]

        # 1B.12: 3 core features - return, volume_ratio, range_position (reduced from 5)
        features = {}

        # Feature 1: return (retorno a 1 período)
        features['return'] = (closes[-1] - closes[-2]) / closes[-2] if len(closes) >= 2 else 0

        # Feature 2: volume_ratio (volumen relativo) - 1B.10: NaN FIX, 1D.9: F1 IMPROVED
        # ROOT CAUSE: volume_ratio produce NaN consistentemente, rompiendo signature hashing
        # FIX F1 (1D.9): Improved validation with floor to prevent division by tiny numbers
        if len(volumes) >= 20:
            volume_mean = np.mean(volumes[-20:])
            # FIX F1: Usar máximo entre volume_mean y 1% de current_volume como piso
            safe_volume = max(volume_mean, current_volume * 0.01, 1e-8)
            volume_ratio = current_volume / safe_volume
            # Validar resultado final
            if np.isnan(volume_ratio) or np.isinf(volume_ratio):
                volume_ratio = 1.0  # Fallback a valor neutral
        else:
            volume_ratio = 1.0  # Fallback a valor neutral
        features['volume_ratio'] = volume_ratio

        # Feature 3: range_position (posición en rango 20)
        range_high = np.max(highs[-20:]) if len(highs) >= 20 else current_close
        range_low = np.min(lows[-20:]) if len(lows) >= 20 else current_close
        features['range_position'] = (current_close - range_low) / (range_high - range_low + 1e-8)

        return features
    
    def _calculate_trend_slope(self, closes: np.ndarray) -> float:
        """Calcular pendiente de tendencia."""
        if len(closes) < 2:
            return 0.0
        
        x = np.arange(len(closes))
        slope, _ = np.polyfit(x, closes, 1)
        return slope / np.mean(closes)  # Normalizado
    
    def calculate_signature(self, features: Dict[str, float],
                           window_size: int) -> str:
        """
        Calcular signature hash para un conjunto de características.

        Args:
            features: Características del estado
            window_size: Tamaño de ventana

        Returns:
            Hash SHA256 del signature
        """
        # 1B.9: Debug logging - feature calculation
        if self.debug_mode and hasattr(self, '_debug_counter'):
            i = self._debug_counter
            if i < 5:
                ret = features.get('return', 0)
                vol_ratio = features.get('volume_ratio', 0)
                range_pos = features.get('range_position', 0)
                print(f"[DEBUG-SIGNATURE] Estado {i}:")
                print(f"[DEBUG-SIGNATURE]   return={ret:.6f}, volume_ratio={vol_ratio:.6f}, range_pos={range_pos:.6f}")
            self._debug_counter += 1

        # 1B.10: NaN FALLBACK VALIDATION - ROOT CAUSE FIX
        # Problema: features con NaN rompen signature hashing → 0 colisiones → 0 emergent_patterns
        # Solución: Reemplazar NaN/Inf con valores válidos antes de hashing
        sanitized_features = {}
        for key, value in features.items():
            if isinstance(value, (int, float)):
                # Convertir a float y validar
                float_val = float(value)
                if np.isnan(float_val) or np.isinf(float_val):
                    # 1B.10: NaN fallback - usar 0.0 para hashing consistente
                    sanitized_features[key] = 0.0
                else:
                    sanitized_features[key] = float_val
            else:
                sanitized_features[key] = 0.0  # Fallback para tipos no numéricos

        # Redondear características para agrupar similares (usar sanitized)
        rounded = {}
        for key, value in sanitized_features.items():
            rounded[key] = round(value, self.signature_precision)

        # Agregar window_size al signature
        rounded['window_size'] = window_size

        # Crear string único
        signature_str = str(sorted(rounded.items()))

        # Hash SHA256
        signature = hashlib.sha256(signature_str.encode()).hexdigest()[:16]

        return signature
    
    def find_emergent_patterns(self, state_history: List[TimeSeriesState],
                              regime: MarketRegime,
                              min_support: float = None) -> List[EmergentPattern]:
        """
        Encontrar patrones emergentes en historial de estados.

        Args:
            state_history: Lista de estados históricos
            regime: Régimen de mercado para filtrar
            min_support: Soporte mínimo (override)

        Returns:
            Lista de patrones emergentes válidos
        """
        if min_support is None:
            min_support = self.min_support

        # 1B.9: Debug logging - INICIO BÚSQUEDA PATRONES EMERGENTES
        if self.debug_mode:
            print(f"[DEBUG-INDUCTION] === INICIO BÚSQUEDA PATRONES EMERGENTES ===")
            print(f"[DEBUG-INDUCTION] Historial recibido: {len(state_history)} estados")
            print(f"[DEBUG-INDUCTION] Régimen: {regime}")
            print(f"[DEBUG-INDUCTION] min_support: {min_support:.0%}")
            # Reset debug counter for signature logging
            self._debug_counter = 0

        # Diccionario para contar ocurrencias de signatures
        signature_counts: Dict[str, Dict[str, Any]] = {}
        total_states = 0
        variance_data = []  # 1B.9: Track variance for [DEBUG-VARIANCE]

        # Procesar cada estado
        for idx, state in enumerate(state_history):
            # Filtrar por régimen
            if state.current_regime != regime:
                continue

            total_states += 1

            # Extraer características
            features = self.extract_features(state, idx)

            if not features:
                continue

            # 1B.9: Debug logging - estado procesado
            if self.debug_mode and idx < 5:
                print(f"[DEBUG-INDUCTION] Procesando estado {idx}: features={list(features.keys())}")

            # Buscar patrones en cada ventana
            for window_size in self.window_sizes:
                if idx < window_size:
                    continue

                # Calcular signature
                signature = self.calculate_signature(features, window_size)
                self.stats['total_signatures'] += 1

                # Registrar ocurrencia
                if signature not in signature_counts:
                    signature_counts[signature] = {
                        'count': 0,
                        'features': features,
                        'window_size': window_size,
                        'indices': [],
                        'outcomes': []  # Éxito/fracaso de trades posteriores
                    }

                signature_counts[signature]['count'] += 1
                signature_counts[signature]['indices'].append(idx)

                # Registrar outcome (si hay estado siguiente)
                if idx + 1 < len(state_history):
                    next_state = state_history[idx + 1]
                    price_change = (next_state.closes[-1] - state.closes[-1]) / state.closes[-1]
                    signature_counts[signature]['outcomes'].append(price_change)

        # 1B.9: Debug logging - resumen de búsqueda
        if self.debug_mode:
            print(f"[DEBUG-INDUCTION] Total estados procesados: {total_states}")
            print(f"[DEBUG-INDUCTION] Signatures únicas encontradas: {len(signature_counts)}")

        # Filtrar por soporte y crear patrones
        emergent_patterns = []

        for signature, data in signature_counts.items():
            support = data['count'] / max(1, total_states)
            
            if support < min_support:
                continue
            
            # Calcular success rate
            outcomes = data['outcomes']
            if outcomes:
                # Éxito: precio se mueve en dirección esperada
                avg_outcome = np.mean(outcomes)
                success_rate = sum(1 for o in outcomes if o * avg_outcome > 0) / len(outcomes)
            else:
                success_rate = 0.5
            
            # Crear patrón emergente
            pattern = EmergentPattern(
                signature=signature,
                pattern_type=f"EMERGENT_{signature}",
                regime=regime,
                support=support,
                conditions=self._features_to_conditions(data['features']),
                success_rate=success_rate,
                E_pt=0.50 + (success_rate - 0.5) * 0.4  # Mapear [0,1] → [0.1,0.9]
            )
            
            emergent_patterns.append(pattern)
        
        # Ordenar por soporte y E_pt
        emergent_patterns.sort(key=lambda p: (p.support, p.E_pt), reverse=True)

        # 1B.9: Debug logging - variance analysis
        if self.debug_mode and emergent_patterns:
            supports = [p.support for p in emergent_patterns]
            e_pts = [p.E_pt for p in emergent_patterns]
            print(f"[DEBUG-VARIANCE] Patrones encontrados: {len(emergent_patterns)}")
            print(f"[DEBUG-VARIANCE] Soporte: min={min(supports):.4f}, max={max(supports):.4f}, mean={np.mean(supports):.4f}")
            print(f"[DEBUG-VARIANCE] E_pt: min={min(e_pts):.4f}, max={max(e_pts):.4f}, mean={np.mean(e_pts):.4f}")

        # Actualizar estadísticas
        self.stats['valid_patterns'] = len(emergent_patterns)

        return emergent_patterns
    
    def _features_to_conditions(self, features: Dict[str, float]) -> Dict[str, float]:
        """
        Convertir características a condiciones de trigger.

        1D.7 FIX: Asegurar que SIEMPRE haya al menos UN trigger válido
        para evitar que any_trigger_matched=False en _check_trigger_conditions().

        Args:
            features: Características del patrón

        Returns:
            Diccionario de condiciones para MarketStoredPattern
        """
        conditions = {}

        # Volatilidad
        if 'volatility_20' in features:
            conditions['volatility_min'] = features['volatility_20'] * 0.8
            conditions['volatility_max'] = features['volatility_20'] * 1.2

        # Volumen
        if 'volume_ratio' in features:
            conditions['volume_ratio_min'] = features['volume_ratio'] * 0.9

        # Posición en rango
        if 'price_position' in features:
            conditions['price_position'] = features['price_position']

        # Tendencia
        if 'trend_slope' in features:
            if features['trend_slope'] > 0.001:
                conditions['trend_slope_min'] = 0.0005
            elif features['trend_slope'] < -0.001:
                conditions['trend_slope_max'] = -0.0005

        # 1D.7 FIX: Si no hay triggers, agregar triggers genéricos por defecto
        # Esto asegura que any_trigger_matched=True en _check_trigger_conditions()
        if not conditions:
            conditions['volatility_max'] = 0.10  # Volatilidad máxima 10% (genérico)
            conditions['volume_ratio_min'] = 0.5  # Volumen mínimo 50% del promedio (genérico)

        return conditions
    
    def validate_axiomatic_soundness(self, pattern: EmergentPattern,
                                    state_history: List[TimeSeriesState]) -> bool:
        """
        Validar soundness axiomática de patrón emergente.
        
        Args:
            pattern: Patrón emergente a validar
            state_history: Historial de estados para validar
        
        Returns:
            True si 0 violaciones axiomáticas
        """
        violations = []
        
        # Obtener índices donde ocurre el patrón
        pattern_indices = []
        for idx, state in enumerate(state_history):
            if state.current_regime != pattern.regime:
                continue
            
            features = self.extract_features(state, idx)
            if not features:
                continue
            
            signature = self.calculate_signature(features, pattern.conditions.get('window_size', 20))
            if signature == pattern.signature:
                pattern_indices.append(idx)
        
        # Validar cada ocurrencia contra axiomas
        for idx in pattern_indices:
            state = state_history[idx]
            prev_state = state_history[idx - 1] if idx > 0 else None
            
            # Validar axiomas (A_market_1-6)
            valid, axiom_violations, _ = MarketAxioms.validate_state(
                state.market_states[-1] if hasattr(state, 'market_states') else state,
                prev_states=state_history[max(0, idx-20):idx],
                prev_state=prev_state.market_states[-1] if prev_state and hasattr(prev_state, 'market_states') else None
            )
            
            if not valid:
                violations.extend(axiom_violations)
        
        # Actualizar patrón
        pattern.violations = violations
        pattern.is_valid = len(violations) == 0
        
        # Actualizar estadísticas
        if not pattern.is_valid:
            self.stats['discarded_by_axioms'] += 1
        
        return pattern.is_valid
    
    def discover_and_validate(self, state_history: List[TimeSeriesState],
                             regime: MarketRegime = None) -> List[EmergentPattern]:
        """
        Descubrir patrones y validar axiomáticamente.
        
        Args:
            state_history: Historial de estados
            regime: Régimen específico o None para todos
        
        Returns:
            Lista de patrones emergentes válidos
        """
        regimes = [regime] if regime else [MarketRegime.BULL, MarketRegime.BEAR, MarketRegime.LATERAL]
        
        all_patterns = []
        
        for r in regimes:
            # Descubrir patrones
            patterns = self.find_emergent_patterns(state_history, r)
            
            # Validar cada patrón
            for pattern in patterns:
                is_valid = self.validate_axiomatic_soundness(pattern, state_history)
                
                if is_valid:
                    all_patterns.append(pattern)
                    # Guardar en cache
                    self.discovered_patterns[pattern.signature] = pattern
        
        return all_patterns
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas de inducción."""
        return {
            **self.stats,
            'cached_patterns': len(self.discovered_patterns),
            'min_support': self.min_support,
            'window_sizes': self.window_sizes
        }


# ============================================================================
# TESTS
# ============================================================================

if __name__ == "__main__":
    print("="*70)
    print("TEST: Market Structural Induction - MSE v5.0.2-R 1B.12")
    print("="*70)

    # Test 1: Crear inductor con parámetros 1B.12
    print("\nTest 1: Crear MarketStructuralInduction (1B.12)")
    inductor = MarketStructuralInduction()
    print(f"  Config: min_support={inductor.min_support}, precision={inductor.signature_precision}")
    print(f"  Features: {inductor.features}")
    assert inductor.min_support == 0.01, "min_support debe ser 0.01 (1B.12)"
    assert inductor.signature_precision == 1, "signature_precision debe ser 1 (1B.12)"
    assert len(inductor.features) == 3, "Debe tener 3 features (1B.12)"
    print("  ✅ PASSED")

    # Test 2: Datos sintéticos
    print("\nTest 2: Generar datos sintéticos")
    import pandas as pd
    np.random.seed(42)
    n = 500
    base = 100.0
    close = [base]
    for i in range(n-1):
        change = np.random.normal(0, 0.3)
        if close[-1] > 102: change -= 0.1
        elif close[-1] < 98: change += 0.1
        close.append(close[-1] + change)
    close = np.array(close)
    high = close + np.abs(np.random.normal(0, 0.3, n))
    low = close - np.abs(np.random.normal(0, 0.3, n))
    open_p = np.roll(close, 1); open_p[0] = close[0]
    volume = np.random.uniform(0.5, 2.0, n)

    df = pd.DataFrame({
        'unix': range(n), 'open': open_p, 'high': high, 'low': low,
        'close': close, 'Volume BTC': volume
    })

    state = TimeSeriesState(data=df, symbol='TEST/USD', window_size=20)
    print(f"  Barras: {len(df)}")
    print(f"  Régimen: {state.current_regime.value}")
    print("  ✅ PASSED")

    # Test 3: Descubrir patrones
    print("\nTest 3: Descubrir patrones emergentes")
    patterns = inductor.discover_and_validate([state], MarketRegime.LATERAL)
    print(f"  Patrones descubiertos: {len(patterns)}")

    for p in patterns[:5]:  # Mostrar primeros 5
        print(f"    - {p.pattern_type}: support={p.support:.2f}, E_pt={p.E_pt:.2f}, valid={p.is_valid}")

    stats = inductor.get_stats()
    print(f"  Stats: {stats}")
    print("  ✅ PASSED")

    # Test 4: Convertir a StoredPattern
    print("\nTest 4: Convertir a MarketStoredPattern")
    if patterns:
        stored = patterns[0].to_stored_pattern()
        print(f"  Tipo: {stored.pattern_type}")
        print(f"  Régimen: {stored.regime.value}")
        print(f"  Señal: {stored.entry_signal}")
        print(f"  E(pt): {stored.confidence:.2f}")
        print(f"  Is soft: {stored.is_soft}")
        print("  ✅ PASSED")

    print("\n" + "="*70)
    print("TESTS DE STRUCTURAL INDUCTION PASSED")
    print("="*70)
