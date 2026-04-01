# src/python/market/__init__.py
"""
Módulo de Mercado - MSE v5.0.2-R ETAPA 6
=========================================

Extensión del MSE al dominio financiero.

Módulos:
- axioms: Axiomas formales de mercado (A_market_1 a A_market_6)
- time_series_state: Estado de series temporales (análogo a BoardState)
- market_pattern_database: Base de datos de patrones de mercado
- regime_validator: Validador de regímenes de mercado
- trading_bot: Interface con bots de trading (próximamente)
"""

from .axioms import (
    MarketState,
    MarketRegime,
    MarketAxioms,
    MarketPatternEffectiveness,
    MarketBifurcationHistory
)

from .time_series_state import (
    TimeSeriesState,
    TimeSeriesMetrics,
    load_market_data
)

from .market_pattern_database import (
    MarketPatternDatabase,
    MarketStoredPattern,
    create_builtin_patterns
)

from .trading_bot import (
    TradingBot,
    Backtester,
    BotStrategy,
    OrderType,
    Trade,
    BotPosition,
    BotMetrics
)

__all__ = [
    'MarketState',
    'MarketRegime',
    'MarketAxioms',
    'MarketPatternEffectiveness',
    'MarketBifurcationHistory',
    'TimeSeriesState',
    'TimeSeriesMetrics',
    'load_market_data',
    'MarketPatternDatabase',
    'MarketStoredPattern',
    'create_builtin_patterns',
    'TradingBot',
    'Backtester',
    'BotStrategy',
    'OrderType',
    'Trade',
    'BotPosition',
    'BotMetrics'
]
