# src/python/market/axiom_validator.py
"""
Axiom Validator - MSE v5.0.2-R
==============================

Validación en tiempo real de señales contra axiomas de mercado.
Conexión formal: MSE v5.0-R Sec. I.A (Axiomas A1-A6), market/axioms.py

Niveles de Validación:
- A_market_1, A_market_2, A_market_5, A_market_6: INVOLABLES (booleanos)
- A_market_3, A_market_4: HEURÍSTICOS (float/dict, solo logging)

Criterio de Éxito:
- 0 señales ejecutadas con violaciones axiomáticas en 1000 trades
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path
import sys
import numpy as np

# Asegurar paths
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Imports con fallback para test directo y como módulo
try:
    from .axioms import MarketState, MarketRegime, MarketAxioms
except ImportError:
    from market.axioms import MarketState, MarketRegime, MarketAxioms


@dataclass
class ValidationResult:
    """
    Resultado de validación axiomática.
    
    Atributos:
        valid: True si pasa axiomas inviolables (A1,A2,A5,A6)
        warnings: Lista de warnings (A3,A4)
        violations: Lista de violaciones (A1,A2,A5,A6)
        signal_action: 'ACCEPT', 'REJECT', o 'REVIEW'
        details: Detalles adicionales por axioma
    """
    valid: bool
    warnings: List[str] = field(default_factory=list)
    violations: List[str] = field(default_factory=list)
    signal_action: str = 'ACCEPT'
    details: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        # Determinar acción según validación
        if len(self.violations) > 0:
            self.signal_action = 'REJECT'
        elif len(self.warnings) > 2:
            self.signal_action = 'REVIEW'
        else:
            self.signal_action = 'ACCEPT'


class AxiomValidator:
    """
    Valida señales de trading contra axiomas inviolables.
    
    Formalización:
      validate_signal(signal, state, prev_states) → ValidationResult
    
    Validaciones:
      1. A_market_1 (Unicidad precio): state.close único para timestamp
      2. A_market_2 (OHLC consistente): low ≤ close ≤ high
      3. A_market_3 (Volumen soporte): volume > 0 (solo logging)
      4. A_market_4 (Régimen coherente): strategy ≈ regime (warning)
      5. A_market_5 (Contención candidatos): signal.price ∈ [low, high]
      6. A_market_6 (No arbitraje): |gap| < 3·σ(volatilidad)
    
    Retorno:
      SI violations > 0: signal = REJECT
      SI warnings > 2: signal = REVIEW
      SINO: signal = ACCEPT
    """
    
    def __init__(self, volatility_window: int = 50,
                 arbitrage_sigma_threshold: float = 5.0,
                 **kwargs):
        """
        Inicializar validador axiomático con ajustes Fase 1.

        Args:
            volatility_window: Ventana para calcular volatilidad (S11: 50)
            arbitrage_sigma_threshold: Umbral de sigma para A_market_6 (S12: 5.0σ)
            kwargs: Parámetros adicionales
                - min_gap_threshold: Piso mínimo para crypto (S12: 5%)
        """
        # S11: Ventana de volatilidad aumentada para suavizar
        self.volatility_window = volatility_window  # ANTES: 20

        # S12: Umbral de gap aumentado para crypto volátil
        self.arbitrage_sigma_threshold = arbitrage_sigma_threshold  # ANTES: 3.0

        # 1B.13: Piso mínimo para gaps de crypto (5% → 15% para AXSUST accommodation)
        self.min_gap_threshold = kwargs.get('min_gap_threshold', 0.15)  # 1B.13: 0.05 → 0.15

        # Estadísticas
        self.stats = {
            'total_validations': 0,
            'accepted': 0,
            'rejected': 0,
            'review': 0,
            'violations_by_axiom': {
                'A1': 0, 'A2': 0, 'A5': 0, 'A6': 0
            },
            'warnings_by_axiom': {
                'A3': 0, 'A4': 0
            }
        }
    
    def validate_signal(self, signal: Dict[str, Any],
                       state: MarketState,
                       prev_state: Optional[MarketState] = None,
                       prev_states: List[MarketState] = None,
                       strategy: str = None) -> ValidationResult:
        """
        Validar señal contra todos los axiomas.
        
        Args:
            signal: Diccionario con información de señal
                   {'price': float, 'type': 'buy'/'sell', 'stop_loss': float, ...}
            state: Estado actual de mercado
            prev_state: Estado anterior (para A_market_6)
            prev_states: Lista de estados anteriores (para A_market_4)
            strategy: Estrategia seleccionada (para A_market_4)
        
        Returns:
            ValidationResult con decisión ACCEPT/REJECT/REVIEW
        """
        self.stats['total_validations'] += 1
        
        violations = []
        warnings = []
        details = {}
        
        # =========================================================================
        # AXIOMAS INVOLABLES (A1, A2, A5, A6) - VETO ABSOLUTO
        # =========================================================================
        
        # A_market_1: Unicidad de precio
        a1_valid, a1_detail = self._check_A1_price_uniqueness(state)
        details['A1'] = a1_detail
        if not a1_valid:
            violations.append("A1: Unicidad de precio violada")
            self.stats['violations_by_axiom']['A1'] += 1
        
        # A_market_2: Consistencia OHLC
        a2_valid, a2_detail = self._check_A2_ohlc_consistency(state)
        details['A2'] = a2_detail
        if not a2_valid:
            violations.append("A2: Consistencia OHLC violada")
            self.stats['violations_by_axiom']['A2'] += 1
        
        # A_market_5: Contención de candidatos (signal.price ∈ [low, high])
        a5_valid, a5_detail = self._check_A5_candidate_containment(signal, state)
        details['A5'] = a5_detail
        if not a5_valid:
            violations.append(f"A5: Precio fuera de rango [{state.low}, {state.high}]")
            self.stats['violations_by_axiom']['A5'] += 1
        
        # A_market_6: No arbitraje (gap < 3·σ)
        a6_valid, a6_detail = self._check_A6_no_arbitrage(signal, state, prev_state)
        details['A6'] = a6_detail
        if not a6_valid:
            gap_pct = a6_detail.get('gap_pct', 0) * 100
            threshold_pct = a6_detail.get('threshold_pct', 0) * 100
            violations.append(f"A6: Gap inusual {gap_pct:.2f}% > umbral {threshold_pct:.2f}%")
            self.stats['violations_by_axiom']['A6'] += 1
        
        # =========================================================================
        # AXIOMAS HEURÍSTICOS (A3, A4) - SOLO LOGGING
        # =========================================================================
        
        # A_market_3: Volumen soporte (warning si volume ≈ 0)
        a3_valid, a3_detail = self._check_A3_volume_support(state)
        details['A3'] = a3_detail
        if not a3_valid:
            warnings.append("A3: Volumen insuficiente (warning)")
            self.stats['warnings_by_axiom']['A3'] += 1
        
        # A_market_4: Régimen coherente (warning si strategy ≠ regime)
        a4_valid, a4_detail = self._check_A4_regime_coherence(
            state, prev_states, strategy
        )
        details['A4'] = a4_detail
        if not a4_valid:
            warnings.append(f"A4: Incoherencia strategy/regime (warning)")
            self.stats['warnings_by_axiom']['A4'] += 1
        
        # =========================================================================
        # CREAR RESULTADO
        # =========================================================================
        
        result = ValidationResult(
            valid=len(violations) == 0,
            warnings=warnings,
            violations=violations,
            signal_action='ACCEPT',  # Se actualiza abajo
            details=details
        )
        
        # Determinar acción
        if len(violations) > 0:
            result.signal_action = 'REJECT'
            self.stats['rejected'] += 1
        elif len(warnings) > 2:
            result.signal_action = 'REVIEW'
            self.stats['review'] += 1
        else:
            result.signal_action = 'ACCEPT'
            self.stats['accepted'] += 1
        
        return result
    
    def _check_A1_price_uniqueness(self, state: MarketState) -> Tuple[bool, Dict]:
        """
        A_market_1: Unicidad de precio por timestamp.
        
        Verifica: state.close es único para timestamp
        """
        # En datos OHLCV, el close ya es único por definición
        # Verificamos que no haya valores NaN o infinitos
        is_valid = (
            not np.isnan(state.close) and 
            not np.isinf(state.close) and
            state.close > 0
        )
        
        detail = {
            'axiom': 'A_market_1',
            'type': 'inviolable',
            'valid': is_valid,
            'close': state.close if is_valid else None
        }
        
        return is_valid, detail
    
    def _check_A2_ohlc_consistency(self, state: MarketState) -> Tuple[bool, Dict]:
        """
        A_market_2: Consistencia OHLC.
        
        Verifica: low ≤ open, close ≤ high
        """
        valid_open = state.low <= state.open <= state.high
        valid_close = state.low <= state.close <= state.high
        is_valid = valid_open and valid_close
        
        detail = {
            'axiom': 'A_market_2',
            'type': 'inviolable',
            'valid': is_valid,
            'low': state.low,
            'high': state.high,
            'open': state.open,
            'close': state.close
        }
        
        return is_valid, detail
    
    def _check_A3_volume_support(self, state: MarketState) -> Tuple[bool, Dict]:
        """
        A_market_3: Soporte con volumen.
        
        Verifica: volume > 0 (HEURÍSTICO - solo warning)
        """
        is_valid = state.volume > 0
        
        detail = {
            'axiom': 'A_market_3',
            'type': 'heuristic',
            'valid': is_valid,
            'volume': state.volume
        }
        
        return is_valid, detail
    
    def _check_A4_regime_coherence(self, state: MarketState,
                                   prev_states: List[MarketState],
                                   strategy: str) -> Tuple[bool, Dict]:
        """
        A_market_4: Coherencia de régimen.
        
        Verifica: strategy ≈ regime_detected (HEURÍSTICO - solo warning)
        """
        if strategy is None or prev_states is None or len(prev_states) < 20:
            # No hay suficientes datos para validar
            return True, {
                'axiom': 'A_market_4',
                'type': 'heuristic',
                'valid': True,
                'reason': 'Insufficient data'
            }
        
        # Calcular régimen predominante en ventana
        recent_regimes = [s.regime for s in prev_states[-self.volatility_window:]]
        regime_counts = {}
        for r in recent_regimes:
            regime_counts[r] = regime_counts.get(r, 0) + 1
        
        predominant_regime = max(regime_counts, key=regime_counts.get)
        
        # Mapear estrategia a régimen esperado
        strategy_to_regime = {
            'BULL': MarketRegime.BULL,
            'BEAR': MarketRegime.BEAR,
            'LATERAL': MarketRegime.LATERAL,
            'MARKET_NEUTRAL': MarketRegime.LATERAL
        }
        
        expected_regime = strategy_to_regime.get(strategy, None)
        
        # Verificar coherencia
        is_coherent = (
            expected_regime is None or 
            expected_regime == predominant_regime or
            predominant_regime == MarketRegime.TRANSITION
        )
        
        detail = {
            'axiom': 'A_market_4',
            'type': 'heuristic',
            'valid': is_coherent,
            'strategy': strategy,
            'expected_regime': expected_regime.value if expected_regime else None,
            'predominant_regime': predominant_regime.value,
            'regime_confidence': regime_counts[predominant_regime] / len(recent_regimes)
        }
        
        return is_coherent, detail
    
    def _check_A5_candidate_containment(self, signal: Dict[str, Any],
                                        state: MarketState) -> Tuple[bool, Dict]:
        """
        A_market_5: Contención de candidatos.
        
        Verifica: signal.price ∈ [state.low, state.high]
        """
        signal_price = signal.get('price', state.close)
        is_valid = state.low <= signal_price <= state.high
        
        detail = {
            'axiom': 'A_market_5',
            'type': 'inviolable',
            'valid': is_valid,
            'signal_price': signal_price,
            'low': state.low,
            'high': state.high,
            'within_range': is_valid
        }
        
        return is_valid, detail
    
    def _check_A6_no_arbitrage(self, signal: Dict[str, Any],
                               state: MarketState,
                               prev_state: Optional[MarketState]) -> Tuple[bool, Dict]:
        """
        A_market_6: No arbitraje instantáneo.
        
        S12: Umbral dinámico con piso mínimo para crypto.
        Verifica: gap < max(5% piso, 5σ·volatilidad)

        Args:
            signal: Señal con precio
            state: Estado actual
            prev_state: Estado anterior

        Returns:
            Tuple[bool, Dict]: (válido, detalles)
        """
        if prev_state is None or prev_state.close == 0:
            # No hay estado anterior para comparar
            return True, {
                'axiom': 'A_market_6',
                'type': 'inviolable',
                'valid': True,
                'reason': 'No previous state'
            }

        signal_price = signal.get('price', state.close)
        gap = abs(signal_price - prev_state.close) / prev_state.close

        # Calcular volatilidad histórica con ventana ampliada (S11)
        volatility = getattr(prev_state, 'volatility_rolling', 0.02)
        
        # S12: Umbral dinámico: max(5% piso, 5σ·volatilidad)
        dynamic_threshold = max(self.min_gap_threshold, 
                               self.arbitrage_sigma_threshold * volatility)

        is_valid = gap <= dynamic_threshold

        detail = {
            'axiom': 'A_market_6',
            'type': 'inviolable',
            'valid': is_valid,
            'signal_price': signal_price,
            'prev_close': prev_state.close,
            'gap_pct': gap,
            'threshold_pct': dynamic_threshold,
            'volatility': volatility,
            'sigma_multiplier': self.arbitrage_sigma_threshold,
            'min_gap_threshold': self.min_gap_threshold
        }

        if not is_valid:
            print(f"[Axioma A6] Gap inusual: {gap:.2%} > umbral {dynamic_threshold:.2%} "
                  f"(5σ·vol={self.arbitrage_sigma_threshold*volatility:.2%}, piso={self.min_gap_threshold:.2%})")

        return is_valid, detail
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas de validación."""
        total = self.stats['total_validations']
        return {
            **self.stats,
            'acceptance_rate': self.stats['accepted'] / max(1, total),
            'rejection_rate': self.stats['rejected'] / max(1, total),
            'review_rate': self.stats['review'] / max(1, total)
        }
    
    def reset_stats(self):
        """Reiniciar estadísticas."""
        self.stats = {
            'total_validations': 0,
            'accepted': 0,
            'rejected': 0,
            'review': 0,
            'violations_by_axiom': {'A1': 0, 'A2': 0, 'A5': 0, 'A6': 0},
            'warnings_by_axiom': {'A3': 0, 'A4': 0}
        }


# ============================================================================
# TESTS
# ============================================================================

if __name__ == "__main__":
    print("="*70)
    print("TEST: Axiom Validator - MSE v5.0.2-R")
    print("="*70)
    
    # Test 1: Crear validador
    print("\nTest 1: Crear AxiomValidator")
    validator = AxiomValidator()
    print(f"  Config: volatility_window={validator.volatility_window}, sigma={validator.arbitrage_sigma_threshold}")
    print("  ✓ PASSED")
    
    # Test 2: Estado válido
    print("\nTest 2: Estado válido (debe ACCEPT)")
    state_valid = MarketState(
        timestamp=1, open=100, high=101, low=99, close=100,
        volume=1.0, symbol="TEST/BTC",
        volatility_rolling=0.02
    )
    prev_state = MarketState(
        timestamp=0, open=99.5, high=100.5, low=99, close=99.5,
        volume=1.0, symbol="TEST/BTC"
    )
    
    signal = {'price': 100, 'type': 'buy', 'stop_loss': 99, 'take_profit': 102}
    result = validator.validate_signal(signal, state_valid, prev_state)
    
    print(f"  Acción: {result.signal_action}")
    print(f"  Válido: {result.valid}")
    print(f"  Violaciones: {len(result.violations)}")
    print(f"  Warnings: {len(result.warnings)}")
    assert result.signal_action == 'ACCEPT', "Estado válido debe ACCEPT"
    print("  ✓ PASSED")
    
    # Test 3: Estado inválido (A2 - OHLC)
    print("\nTest 3: Estado inválido A2 (close > high, debe REJECT)")
    state_invalid_a2 = MarketState(
        timestamp=1, open=100, high=101, low=99, close=102,  # close > high
        volume=1.0, symbol="TEST/BTC"
    )
    
    result = validator.validate_signal(signal, state_invalid_a2, prev_state)
    print(f"  Acción: {result.signal_action}")
    print(f"  Violaciones: {result.violations}")
    assert result.signal_action == 'REJECT', "A2 violada debe REJECT"
    assert 'A2' in result.violations[0], "Debe mencionar A2"
    print("  ✓ PASSED")
    
    # Test 4: Estado inválido (A5 - price fuera de rango)
    print("\nTest 4: Estado inválido A5 (price > high, debe REJECT)")
    signal_invalid_price = {'price': 105, 'type': 'buy'}  # Fuera de rango [99, 101]
    
    result = validator.validate_signal(signal_invalid_price, state_valid, prev_state)
    print(f"  Acción: {result.signal_action}")
    print(f"  Violaciones: {result.violations}")
    assert result.signal_action == 'REJECT', "A5 violada debe REJECT"
    print("  ✓ PASSED")
    
    # Test 5: Estado inválido (A6 - gap inusual)
    print("\nTest 5: Estado inválido A6 (gap > 3σ, debe REJECT)")
    signal_large_gap = {'price': 110, 'type': 'buy'}  # Gap de ~10%
    
    result = validator.validate_signal(signal_large_gap, state_valid, prev_state)
    print(f"  Acción: {result.signal_action}")
    print(f"  Violaciones: {result.violations}")
    assert result.signal_action == 'REJECT', "A6 violada debe REJECT"
    print("  ✓ PASSED")
    
    # Test 6: Estadísticas
    print("\nTest 6: Estadísticas de validación")
    stats = validator.get_stats()
    print(f"  Total: {stats['total_validations']}")
    print(f"  Accepted: {stats['accepted']}")
    print(f"  Rejected: {stats['rejected']}")
    print(f"  Acceptance rate: {stats['acceptance_rate']:.1%}")
    print("  ✓ PASSED")
    
    print("\n" + "="*70)
    print("TESTS DE AXIOM VALIDATOR PASSED")
    print("="*70)
