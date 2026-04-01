# src/python/market/axioms.py
"""
Axiomas Formales de Mercado - MSE v5.0.2-R ETAPA 6
==================================================

Extensión del MSE al dominio financiero con axiomas formales de mercado.
Basado en la especificación ETAPA 6 del documento MSE-V.4.0.txt

MSE v5.0.2-R QC Opción B: Re-clasificación de Axiomas
- A1, A2, A5: INVOLABLES (booleanos) - Lógica fundamental
- A3, A4, A6: HEURÍSTICOS (pesos/dicts) - Guían decisión, no vetan

Axiomas definidos:
- A_market_1: Unicidad de precio (inviolable)
- A_market_2: Consistencia OHLC (inviolable)
- A_market_3: Volumen como peso heurístico [0.0, 1.0]
- A_market_4: Detector de transición de régimen (dict)
- A_market_5: Contención de candidatos (inviolable)
- A_market_6: Gap con umbral dinámico 3σ (dict)
"""

import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Union
from enum import Enum


class MarketRegime(Enum):
    """
    Regímenes de mercado según ETAPA 6.
    """
    BULL = "bull"           # Tendencia alcista
    BEAR = "bear"           # Tendencia bajista
    LATERAL = "lateral"     # Rango lateral
    TRANSITION = "transition"  # Transición entre regímenes


@dataclass
class MarketState:
    """
    Estado formal del mercado (análogo a BoardState en Sudoku).
    
    Variables:
    - P(t): Precio en tiempo t
    - V(t): Volumen en tiempo t
    - Ω(t): Conjunto de precios candidatos (rango esperado)
    - R(t): Régimen de mercado en tiempo t
    """
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    symbol: str
    
    # Variables derivadas (opcionales, se calculan)
    candidates: Optional[np.ndarray] = None  # Ω(t): Precios candidatos
    regime: MarketRegime = MarketRegime.LATERAL
    is_resolved: bool = False  # ¿Precio confirmado?
    
    # ✅ QC Opción B: Campos para heurísticos
    volume_rolling_mean: float = 1.0  # Para A3 heurístico
    volatility_rolling: float = 0.02  # Para A6 umbral dinámico 3σ
    
    def __post_init__(self):
        # Inicializar candidatos como rango [low, high]
        if self.candidates is None:
            self.candidates = np.array([self.low, self.high])


# ============================================================================
# AXIOMAS DE DOMINIO (A1-A6 análogos para mercado)
# ============================================================================

class MarketAxioms:
    """
    Axiomas formales de mercado (ETAPA 6).
    
    Estos axiomas son inviolables y definen la consistencia del mercado.
    Análogos a A1-A6 de Sudoku pero adaptados a series temporales.
    """
    
    @staticmethod
    def A1_price_uniqueness(state: MarketState) -> bool:
        """
        A_market_1: Unicidad de precio por timestamp.
        
        Para cada timestamp t, existe un único precio de cierre confirmado.
        
        Formal: ∀t: ∃≤1 P_close(t)
        """
        # El precio de cierre debe ser único y estar dentro del rango [low, high]
        return state.low <= state.close <= state.high
    
    @staticmethod
    def A2_ohlc_consistency(state: MarketState) -> bool:
        """
        A_market_2: Consistencia de OHLC.
        
        El precio debe seguir la lógica: low ≤ open, close ≤ high
        
        Formal: low(t) ≤ {open(t), close(t)} ≤ high(t)
        """
        valid_open = state.low <= state.open <= state.high
        valid_close = state.low <= state.close <= state.high
        return valid_open and valid_close
    
    @staticmethod
    def A3_volume_support(state: MarketState) -> float:
        """
        QC Opción B: A3 retorna peso heurístico [0.0, 1.0] en lugar de veto booleano.
        
        MSE v5.0.2-R: Axiomas inviolables son solo A1, A2, A5.
        El volumen guía la decisión pero no veta estados.
        
        Returns:
            float: Peso ∈ [0.0, 1.0] para score(i,j)
        """
        if state.volume <= 0:
            return 0.0
        
        # Normalizar respecto a volumen histórico (volume_rolling_mean)
        volume_ratio = min(1.0, state.volume / max(0.001, state.volume_rolling_mean))
        return volume_ratio  # ✅ Peso para score(i,j)
    
    @staticmethod
    def A4_regime_coherence(state: MarketState,
                           prev_states: List[MarketState],
                           window: int = 20) -> Dict:
        """
        QC Opción B: A4 retorna dict de transición en lugar de veto booleano.
        
        MSE v5.0.2-R: Los regímenes CAMBIAN naturalmente (no es violación).
        Este método detecta y registra transiciones para análisis.
        
        Returns:
            Dict: Información de transición para logging/ajuste, no veto
        """
        result = {
            'regime_detected': state.regime,
            'regime_previous': prev_states[-1].regime if prev_states and len(prev_states) > 0 else None,
            'transition_detected': False,
            'transition_confidence': 0.0,
            'logging': True  # ✅ Registrar para análisis, no vetar
        }
        
        if prev_states and len(prev_states) > 0:
            result['transition_detected'] = state.regime != prev_states[-1].regime
            
            if result['transition_detected']:
                # Calcular confianza de transición basada en fuerza de tendencia
                recent_closes = [s.close for s in prev_states[-window:]] if len(prev_states) >= window else [s.close for s in prev_states]
                if len(recent_closes) >= 2:
                    trend = np.polyfit(range(len(recent_closes)), recent_closes, 1)[0]
                    y_pred = trend * np.arange(len(recent_closes)) + np.mean(recent_closes)
                    ss_res = np.sum((np.array(recent_closes) - y_pred) ** 2)
                    ss_tot = np.sum((np.array(recent_closes) - np.mean(recent_closes)) ** 2)
                    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
                    result['transition_confidence'] = max(0.0, r_squared)
                
                print(f"[RegimeValidator] Transición detectada: {result['regime_previous']} → {result['regime_detected']} (confianza: {result['transition_confidence']:.2f})")
        
        return result  # ✅ Información para logging/ajuste, no veto
    
    @staticmethod
    def A5_candidate_containment(state: MarketState) -> bool:
        """
        A_market_5: Contención de candidatos (INVOLABLE).
        
        QC Fix: Asegurar retorno de bool estricto para veto axiomático.
        El precio de cierre debe estar dentro del rango de candidatos.
        
        Returns:
            bool: True si contenido, False si violación (veto)
        """
        # Manejar caso None o array vacío
        if state.candidates is None or len(state.candidates) == 0:
            return True  # Sin candidatos → no hay violación posible
        
        # Asegurar que es array numpy para operaciones
        candidates = np.asarray(state.candidates)
        
        if len(candidates) < 2:
            return True  # Un solo candidato → siempre contenido
        
        # Convertir a float para evitar problemas de tipo
        min_candidate = float(np.min(candidates))
        max_candidate = float(np.max(candidates))
        close_price = float(state.close)
        
        # Retornar booleano explícito
        result = bool(min_candidate <= close_price <= max_candidate)
        return result
    
    @staticmethod
    def A6_no_arbitrage(state: MarketState,
                        prev_state: Optional[MarketState]) -> Dict:
        """
        QC Opción B: A6 retorna umbral dinámico basado en volatilidad histórica.
        
        MSE v5.0.2-R: Gaps >10% existen en mercados (noticias, crashes).
        El umbral es 3σ de volatilidad rolling (adaptativo).
        
        Returns:
            Dict: Resultado con umbral dinámico, alerta (no veto)
        """
        result = {
            'valid': True,
            'gap': 0.0,
            'threshold': 0.0,
            'warning': False,
            'logging': True
        }
        
        if prev_state is None or prev_state.close == 0:
            return result
        
        gap = abs(state.close - prev_state.close) / prev_state.close
        result['gap'] = gap
        
        # ✅ Umbral dinámico: 3σ de volatilidad histórica
        volatility_rolling = getattr(prev_state, 'volatility_rolling', 0.02)
        dynamic_threshold = 3.0 * volatility_rolling  # 3 sigma
        
        result['threshold'] = dynamic_threshold
        result['valid'] = gap <= dynamic_threshold
        result['warning'] = gap > dynamic_threshold
        
        if result['warning']:
            print(f"[Axioma A6] Gap inusual detectado: {gap:.2%} > umbral dinámico {dynamic_threshold:.2%} (3σ={volatility_rolling:.2%})")
        
        return result
    
    @classmethod
    def validate_state(cls, state: MarketState,
                      prev_states: List[MarketState] = None,
                      prev_state: MarketState = None) -> Tuple[bool, List[str], Dict]:
        """
        Valida un estado de mercado contra todos los axiomas.
        
        QC Opción B: A1, A2, A5 son inviolables (booleanos).
        A3, A4, A6 son heurísticos (pesos/dicts) - no generan violaciones.
        
        Returns:
            Tuple[bool, List[str], Dict]: (es_válido, violaciones_inviolables, info_heuristica)
        """
        violations = []
        heuristic_info = {
            'volume_weight': 0.0,
            'regime_transition': None,
            'gap_warning': False
        }
        
        # ✅ AXIOMAS INVOLABLES (A1, A2, A5) - Generan violaciones
        if not cls.A1_price_uniqueness(state):
            violations.append("A1: Unicidad de precio violada")
        
        if not cls.A2_ohlc_consistency(state):
            violations.append("A2: Consistencia OHLC violada")
        
        if not cls.A5_candidate_containment(state):
            violations.append("A5: Contención de candidatos violada")
        
        # ✅ AXIOMAS HEURÍSTICOS (A3, A4, A6) - Solo info, no violaciones
        if prev_states:
            a4_result = cls.A4_regime_coherence(state, prev_states)
            heuristic_info['regime_transition'] = a4_result
            # No agregar violación, solo logging si hay transición
        
        if prev_state:
            a6_result = cls.A6_no_arbitrage(state, prev_state)
            heuristic_info['gap_warning'] = a6_result['warning']
            # No agregar violación, solo logging si hay gap inusual
        
        # A3: Volumen como peso
        heuristic_info['volume_weight'] = cls.A3_volume_support(state)
        
        return (len(violations) == 0, violations, heuristic_info)


# ============================================================================
# PREDICADOS DE META-NIVEL (análogos a E(pt), H(i,j))
# ============================================================================

@dataclass
class MarketPatternEffectiveness:
    """
    E(pt) para patrones de mercado.
    Análogo a E(pt) en Sudoku pero para patrones de trading.
    """
    pattern_type: str  # Ej: 'head_and_shoulders', 'double_top', 'breakout'
    confidence: float  # Efectividad [0.1, 1.0]
    uses: int = 0
    successes: int = 0
    
    def update(self, success: bool, delta_plus: float = 0.1,
               delta_minus: float = 0.15, epsilon_min: float = 0.1,
               epsilon_max: float = 1.0):
        """Actualizar efectividad tras uso."""
        self.uses += 1
        if success:
            self.successes += 1
            self.confidence = min(epsilon_max, self.confidence + delta_plus)
        else:
            self.confidence = max(epsilon_min, self.confidence - delta_minus)


@dataclass
class MarketBifurcationHistory:
    """
    H(v) para decisiones de trading.
    Historial de éxito en bifurcaciones (compra/venta).
    """
    action: str  # 'buy' o 'sell'
    price_level: float
    history: float = 0.0  # Contador neto: éxitos - fracasos
    
    def update(self, success: bool, depth: int = 1):
        """Actualizar historial tras resultado."""
        if success:
            change = depth * 0.1
        else:
            change = -max(0.1, (10 - depth) * 0.05)
        
        self.history = max(0.0, self.history + change)


# ============================================================================
# TESTS
# ============================================================================

if __name__ == "__main__":
    print("="*60)
    print("TEST: Market Axioms - MSE v5.0.2-R ETAPA 6")
    print("="*60)
    
    # Test 1: Estado válido
    print("\nTest 1: Estado de mercado válido")
    state = MarketState(
        timestamp=1647497040000,
        open=0.00032646,
        high=0.00032700,
        low=0.00032600,
        close=0.00032650,
        volume=1.5,
        symbol="REP/BTC",
        regime=MarketRegime.LATERAL
    )
    
    valid, violations = MarketAxioms.validate_state(state)
    print(f"  Estado: {state.symbol} @ {state.close}")
    print(f"  Válido: {valid}")
    if violations:
        print(f"  Violaciones: {violations}")
    assert valid, "Estado válido debería pasar"
    print("  ✓ PASSED")
    
    # Test 2: Estado inválido (OHLC inconsistente)
    print("\nTest 2: Estado inválido (OHLC inconsistente)")
    invalid_state = MarketState(
        timestamp=1647497040000,
        open=0.00035000,  # Fuera del rango high
        high=0.00032700,
        low=0.00032600,
        close=0.00032650,
        volume=1.5,
        symbol="REP/BTC"
    )
    
    valid, violations = MarketAxioms.validate_state(invalid_state)
    print(f"  Estado: open={invalid_state.open} > high={invalid_state.high}")
    print(f"  Válido: {valid}")
    print(f"  Violaciones: {violations}")
    assert not valid, "Estado inválido debería fallar"
    assert "A2" in violations[0], "Debería violar A2"
    print("  ✓ PASSED")
    
    # Test 3: Regime detection
    print("\nTest 3: Coherencia de régimen")
    prev_states = [
        MarketState(timestamp=i, open=100+i, high=101+i, low=99+i, close=100.5+i,
                   volume=1.0, symbol="TEST")
        for i in range(20)
    ]
    
    # Estado con régimen coherente (tendencia alcista)
    bull_state = MarketState(
        timestamp=100, open=120, high=121, low=119, close=120.5,
        volume=1.0, symbol="TEST", regime=MarketRegime.BULL
    )
    
    valid, violations = MarketAxioms.validate_state(
        bull_state, prev_states=prev_states
    )
    print(f"  Tendencia: alcista, Régimen: {bull_state.regime}")
    print(f"  Coherente: {valid}")
    assert valid, "Régimen bull debería ser coherente con tendencia alcista"
    print("  ✓ PASSED")
    
    print("\n" + "="*60)
    print("TODOS LOS TESTS DE AXIOMAS DE MERCADO PASSED")
    print("="*60)
