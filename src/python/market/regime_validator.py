# src/python/market/regime_validator.py
"""
Regime Validator - MSE v5.0.2-R (R01-R03)
==========================================

Validador de regímenes de mercado para clasificación BULL/BEAR/LATERAL/TRANSITION.
Implementa detección basada en Z-Score, volatilidad y tendencia.

Conexión Formal:
- R01: Z-Score threshold más permisivo (0.02)
- R02: Volatilidad threshold más permisivo (0.03)
- R03: Ventana de tendencia ampliada (50 barras)

Referencia: Manual Oficial v5.0.2-R, Volumen III, Sección 2.2
"""

import numpy as np
from typing import Dict, List, Optional, Any
from pathlib import Path
import sys

# Asegurar paths
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# IMPORTAR MarketRegime DE axioms.py (NO definir el nuestro propio)
from src.python.market.axioms import MarketRegime


class RegimeValidator:
    """
    Validador de regímenes de mercado.
    
    Clasifica el estado del mercado en uno de los regímenes definidos
    basándose en:
    1. Z-Score de retornos (R01)
    2. Volatilidad reciente (R02)
    3. Tendencia de medias móviles (R03)
    
    Umbrales ajustados para crypto (más permisivos que tradicionales).
    """
    
    def __init__(self, **kwargs):
        """
        Inicializar validador de regímenes.

        Args:
            z_score_threshold: Threshold para Z-Score (R01: 0.08)
            volatility_threshold: Threshold para volatilidad (R02: 0.08)
            trend_window: Ventana para tendencia (R03: 50)
            ema_short: EMA corta para cruces (20)
            ema_long: EMA larga para cruces (50)
            trend_strength_threshold: Threshold para fuerza de tendencia (1B.6: 0.005)
        """
        # R01: Z-Score threshold más permisivo (1B.6: 0.05 → 0.08)
        self.z_score_threshold = kwargs.get('z_score_threshold', 0.08)  # 1B.6: 0.05 → 0.08 (60% más permisivo)

        # R02: Volatilidad threshold más permisivo (1B.6: 0.05 → 0.08)
        self.volatility_threshold = kwargs.get('volatility_threshold', 0.08)  # 1B.6: 0.05 → 0.08 (60% más permisivo)

        # R03: Ventana de tendencia ampliada
        self.trend_window = kwargs.get('trend_window', 50)  # ANTES: 20

        # EMAs para cruces de tendencia
        self.ema_short = kwargs.get('ema_short', 20)
        self.ema_long = kwargs.get('ema_long', 50)

        # 1B.6: NUEVO - Threshold para detectar tendencias incipientes
        self.trend_strength_threshold = kwargs.get('trend_strength_threshold', 0.005)  # NUEVO en 1B.6 (ajustado de 0.02 → 0.005 para crypto)

        # Historial de regímenes para detección de transición
        self.regime_history: List[MarketRegime] = []
        self.max_history = 10
    
    def classify(self, state_history: List[Any]) -> MarketRegime:
        """
        Clasificar régimen de mercado basado en historial de estados.
        
        Args:
            state_history: Lista de estados (TimeSeriesState o similar)
        
        Returns:
            MarketRegime: Régimen clasificado
        
        R01-R03: Detección con umbrales ajustados para crypto
        """
        if len(state_history) < self.trend_window:
            # Insuficientes datos para clasificación confiable
            return MarketRegime.LATERAL
        
        # Extraer closes de la ventana de tendencia
        closes = np.array([s.close for s in state_history[-self.trend_window:]])
        
        # Calcular retornos
        returns = np.diff(closes) / (closes[:-1] + 1e-8)
        
        # =========================================================================
        # R01: Z-Score de retornos
        # =========================================================================
        mean_return = np.mean(returns)
        std_return = np.std(returns) + 1e-8
        z_score = mean_return / std_return
        
        # =========================================================================
        # R02: Volatilidad
        # =========================================================================
        volatility = std_return
        
        # =========================================================================
        # R03: Tendencia (pendiente de EMA)
        # =========================================================================
        ema_short_val = self._calculate_ema(closes, self.ema_short)
        ema_long_val = self._calculate_ema(closes, self.ema_long)
        ema_diff = (ema_short_val - ema_long_val) / (ema_long_val + 1e-8)

        # =========================================================================
        # 1B.6: NUEVO - Trend Strength (fuerza de tendencia)
        # =========================================================================
        # Calcular trend_strength como la diferencia normalizada entre EMAs
        # Esto detecta tendencias incipientes antes de que sean evidentes en Z-Score
        trend_strength = abs(ema_short_val - ema_long_val) / (ema_long_val + 1e-8)

        # =========================================================================
        # Clasificación con umbrales ajustados
        # =========================================================================
        regime = MarketRegime.LATERAL  # Default

        # 1B.6: PRIORIDAD 1 - Verificar trend_strength primero para detectar tendencias incipientes
        if trend_strength > self.trend_strength_threshold:
            # Tendencia incipiente detectada por cruce de EMAs
            if ema_short_val > ema_long_val:
                regime = MarketRegime.BULL
            else:
                regime = MarketRegime.BEAR

        # R01-R02: Verificar Z-Score y volatilidad (si aún no se detectó tendencia)
        elif abs(z_score) > self.z_score_threshold:
            # Tendencia clara detectada por Z-Score
            if z_score > 0:
                regime = MarketRegime.BULL
            else:
                regime = MarketRegime.BEAR

        elif volatility > self.volatility_threshold:
            # Alta volatilidad sin tendencia clara
            regime = MarketRegime.VOLATILE

        # R03: Verificar cruces de EMA para confirmación adicional (fallback)
        if regime == MarketRegime.LATERAL:
            if ema_diff > 0.01:  # EMA corta > EMA larga (alcista)
                regime = MarketRegime.BULL
            elif ema_diff < -0.01:  # EMA corta < EMA larga (bajista)
                regime = MarketRegime.BEAR
        
        # Detectar transición de régimen
        if len(self.regime_history) > 0:
            last_regime = self.regime_history[-1]
            if last_regime != regime and last_regime != MarketRegime.TRANSITION:
                # Cambio de régimen detectado
                regime = MarketRegime.TRANSITION

        # Actualizar historial
        self.regime_history.append(regime)
        if len(self.regime_history) > self.max_history:
            self.regime_history.pop(0)

        # 1C.2: Logging desactivado para evitar I/O bottleneck durante tests
        # Logging solo para debug específico cuando sea necesario
        # if len(self.regime_history) > 1 and self.regime_history[-2] != regime:
        #     print(f"[RegimeValidator] CAMBIO: {self.regime_history[-2].value if len(self.regime_history) > 1 else 'N/A'} → {regime.value} | "
        #           f"Z-Score: {z_score:.4f} | Vol: {volatility:.4f}")

        return regime
    
    def _calculate_ema(self, prices: List[float], period: int) -> float:
        """
        Calcular EMA (Exponential Moving Average).
        
        Args:
            prices: Lista de precios
            period: Período de la EMA
        
        Returns:
            float: Valor de la EMA
        """
        if len(prices) < period:
            return np.mean(prices)  # Fallback a SMA si no hay suficientes datos
        
        # Calcular multiplicador
        multiplier = 2 / (period + 1)
        
        # Iniciar con SMA
        ema = np.mean(prices[:period])
        
        # Calcular EMA iterativamente
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        
        return ema
    
    def get_regime_distribution(self) -> Dict[str, float]:
        """
        Obtener distribución de regímenes en historial.
        
        Returns:
            Dict[str, float]: Porcentaje de cada régimen
        """
        if not self.regime_history:
            return {}
        
        distribution = {}
        for regime in self.regime_history:
            key = regime.value
            distribution[key] = distribution.get(key, 0) + 1
        
        # Convertir a porcentajes
        total = len(self.regime_history)
        for key in distribution:
            distribution[key] = distribution[key] / total * 100
        
        return distribution
    
    def is_lateral(self, state_history: List[Any]) -> bool:
        """
        Verificar si el régimen actual es LATERAL.
        
        Args:
            state_history: Historial de estados
        
        Returns:
            bool: True si es LATERAL
        """
        regime = self.classify(state_history)
        return regime in [MarketRegime.LATERAL, MarketRegime.TRANSITION]
    
    def is_trending(self, state_history: List[Any]) -> bool:
        """
        Verificar si hay tendencia clara (BULL o BEAR).
        
        Args:
            state_history: Historial de estados
        
        Returns:
            bool: True si hay tendencia
        """
        regime = self.classify(state_history)
        return regime in [MarketRegime.BULL, MarketRegime.BEAR]
    
    def get_config(self) -> Dict[str, Any]:
        """
        Obtener configuración actual del validador.

        Returns:
            Dict[str, Any]: Configuración con thresholds
        """
        return {
            'z_score_threshold': self.z_score_threshold,
            'volatility_threshold': self.volatility_threshold,
            'trend_strength_threshold': self.trend_strength_threshold,  # 1B.6: NUEVO
            'trend_window': self.trend_window,
            'ema_short': self.ema_short,
            'ema_long': self.ema_long
        }


# ============================================================================
# TESTS
# ============================================================================

if __name__ == "__main__":
    print("="*70)
    print("TEST: Regime Validator - MSE v5.0.2-R (R01-R03)")
    print("="*70)
    
    # Crear datos sintéticos para test
    np.random.seed(42)
    
    # Test 1: Crear validador
    print("\nTest 1: Crear RegimeValidator")
    validator = RegimeValidator()
    config = validator.get_config()
    print(f"  z_score_threshold: {config['z_score_threshold']}")
    print(f"  volatility_threshold: {config['volatility_threshold']}")
    print(f"  trend_window: {config['trend_window']}")
    assert config['z_score_threshold'] == 0.02, "R01 fallido"
    assert config['volatility_threshold'] == 0.03, "R02 fallido"
    assert config['trend_window'] == 50, "R03 fallido"
    print("  ✅ PASSED")
    
    # Test 2: Clasificar régimen LATERAL
    print("\nTest 2: Clasificar régimen LATERAL")
    
    # Generar datos laterales (rango estrecho)
    lateral_data = []
    base_price = 100
    for i in range(100):
        price = base_price + np.random.normal(0, 0.5)  # Poco movimiento
        lateral_data.append(type('State', (), {'close': price})())
    
    regime = validator.classify(lateral_data)
    print(f"  Régimen detectado: {regime.value}")
    assert regime in [MarketRegime.LATERAL, MarketRegime.VOLATILE], "Debería ser LATERAL"
    print("  ✅ PASSED")
    
    # Test 3: Clasificar régimen BULL
    print("\nTest 3: Clasificar régimen BULL")
    
    # Generar datos alcistas
    bull_data = []
    base_price = 100
    for i in range(100):
        price = base_price + i * 0.5 + np.random.normal(0, 0.3)  # Tendencia alcista
        bull_data.append(type('State', (), {'close': price})())
    
    regime = validator.classify(bull_data)
    print(f"  Régimen detectado: {regime.value}")
    assert regime == MarketRegime.BULL, "Debería ser BULL"
    print("  ✅ PASSED")
    
    # Test 4: Clasificar régimen BEAR
    print("\nTest 4: Clasificar régimen BEAR")
    
    # Generar datos bajistas
    bear_data = []
    base_price = 100
    for i in range(100):
        price = base_price - i * 0.5 + np.random.normal(0, 0.3)  # Tendencia bajista
        bear_data.append(type('State', (), {'close': price})())
    
    regime = validator.classify(bear_data)
    print(f"  Régimen detectado: {regime.value}")
    assert regime == MarketRegime.BEAR, "Debería ser BEAR"
    print("  ✅ PASSED")
    
    # Test 5: Distribución de regímenes
    print("\nTest 5: Distribución de regímenes")
    distribution = validator.get_regime_distribution()
    print(f"  Distribución: {distribution}")
    assert len(distribution) > 0, "Debería tener distribución"
    print("  ✅ PASSED")
    
    print("\n" + "="*70)
    print("TESTS DE REGIME VALIDATOR PASSED")
    print("="*70)
