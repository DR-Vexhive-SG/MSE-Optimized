# src/python/market/trading_bot.py
"""
Trading Bot Interface - MSE v5.0.2-R ETAPA 6
============================================

Interface para bots de trading que operan con el framework MSE.
Permite:
- Estrategias alcistas, bajistas y paralelas
- Ejecución de órdenes basada en patrones MSE
- Backtesting y forward testing
- Integración con exchanges (Binance, Bitfinex, etc.)

ETAPA 6: Bots dan tiempo de implementar estrategias
"""

import numpy as np
import torch
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import time
from pathlib import Path
import sys

# Asegurar paths
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.python.market.axioms import MarketRegime, MarketState
from src.python.market.time_series_state import TimeSeriesState
from src.python.market.market_pattern_database import MarketPatternDatabase, MarketStoredPattern

# Imports con fallback para módulo meta
try:
    from .meta.trading_meta_learner import TradingMetaLearner
    from .meta.forward_forward import ForwardForwardLearner, integrate_with_trading_bot
    from .regime_validator import RegimeValidator, MarketRegime
except ImportError:
    from src.python.market.meta.trading_meta_learner import TradingMetaLearner
    from src.python.market.meta.forward_forward import ForwardForwardLearner, integrate_with_trading_bot
    from src.python.market.regime_validator import RegimeValidator, MarketRegime


# ============================================================================
# ENUMS Y ESTRUCTURAS
# ============================================================================

class BotStrategy(Enum):
    """Estrategias de trading soportadas."""
    BULL = "bull"           # Alcista (solo compras)
    BEAR = "bear"           # Bajista (solo ventas)
    PARALLEL = "parallel"   # Paralela (compras y ventas simultáneas)
    MARKET_NEUTRAL = "market_neutral"  # Neutral (arbitraje, range trading)


class OrderType(Enum):
    """Tipos de orden."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class Trade:
    """Operación ejecutada."""
    timestamp: int
    symbol: str
    order_type: OrderType
    price: float
    amount: float
    regime: MarketRegime
    pattern_used: str
    stop_loss: float
    take_profit: float
    
    # Resultado (se completa al cerrar)
    close_price: Optional[float] = None
    close_timestamp: Optional[int] = None
    pnl: float = 0.0  # Profit & Loss
    pnl_pct: float = 0.0
    is_closed: bool = False
    
    def close(self, close_price: float, close_timestamp: int):
        """Cerrar operación y calcular PnL."""
        self.close_price = close_price
        self.close_timestamp = close_timestamp
        self.is_closed = True
        
        if self.order_type == OrderType.BUY:
            # Long: ganancia si precio sube
            self.pnl = (close_price - self.price) * self.amount
            self.pnl_pct = (close_price / self.price - 1) * 100
        else:
            # Short: ganancia si precio baja
            self.pnl = (self.price - close_price) * self.amount
            self.pnl_pct = (1 - close_price / self.price) * 100
    
    def __repr__(self):
        status = "CLOSED" if self.is_closed else "OPEN"
        return f"Trade({self.order_type.value} {self.symbol} @ {self.price}, {status}, PnL={self.pnl_pct:.2f}%)"


@dataclass
class BotPosition:
    """Posición actual del bot."""
    symbol: str
    amount: float
    entry_price: float
    entry_timestamp: int
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    # Triple Barrier parameters
    stop_loss_pct: float = 0.02  # Stop loss porcentual
    take_profit_pct: float = 0.04  # Take profit porcentual
    bars_held: int = 0  # Barras mantenidas
    # REINFORCE: Store strategy info for episode recording at exit
    strategy: str = ""  # Strategy used to open this position
    log_prob: float = 0.0  # Log-probability of strategy selection
    regime: str = ""  # Market regime at entry
    patterns_used: List[str] = field(default_factory=list)  # Patterns used

    def update_price(self, price: float):
        """Actualizar precio y PnL no realizado."""
        self.current_price = price
        if self.amount > 0:
            # Long
            self.unrealized_pnl = (price - self.entry_price) * self.amount
            self.unrealized_pnl_pct = (price / self.entry_price - 1) * 100
        else:
            # Short
            self.unrealized_pnl = (self.entry_price - price) * abs(self.amount)
            self.unrealized_pnl_pct = (1 - price / self.entry_price) * 100


@dataclass
class BotMetrics:
    """Métricas de rendimiento del bot."""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    win_rate: float = 0.0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    
    # Por régimen
    regime_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    def update(self, trade: Trade):
        """Actualizar métricas tras cerrar trade."""
        if not trade.is_closed:
            return
        
        self.total_trades += 1
        self.total_pnl += trade.pnl
        
        if trade.pnl > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1
        
        self.win_rate = self.winning_trades / max(1, self.total_trades)
        
        # Actualizar stats por régimen
        regime_key = trade.regime.value
        if regime_key not in self.regime_stats:
            self.regime_stats[regime_key] = {
                'trades': 0, 'wins': 0, 'total_pnl': 0.0
            }
        
        self.regime_stats[regime_key]['trades'] += 1
        if trade.pnl > 0:
            self.regime_stats[regime_key]['wins'] += 1
        self.regime_stats[regime_key]['total_pnl'] += trade.pnl


# ============================================================================
# TRADING BOT
# ============================================================================

class TradingBot:
    """
    Bot de trading basado en MSE.
    
    ETAPA 6:
    - Usa patrones MSE para decisiones
    - Soporta estrategias alcistas, bajistas y paralelas
    - Ejecuta órdenes con stop loss y take profit
    - Trackea métricas de rendimiento
    """
    
    def __init__(self, strategy: BotStrategy, symbol: str,
                 initial_capital: float = 10000.0,
                 pattern_db: Optional[MarketPatternDatabase] = None):
        """
        Inicializar bot.
        
        Args:
            strategy: Estrategia (BULL, BEAR, PARALLEL, MARKET_NEUTRAL)
            symbol: Par a operar (ej: 'REP/BTC')
            initial_capital: Capital inicial
            pattern_db: Base de datos de patrones (opcional)
        """
        self.strategy = strategy
        self.symbol = symbol
        self.capital = initial_capital
        self.initial_capital = initial_capital
        self.pattern_db = pattern_db or MarketPatternDatabase()
        
        # Estado actual
        self.current_regime = MarketRegime.LATERAL
        self.position: Optional[BotPosition] = None
        self.open_trades: List[Trade] = []
        self.closed_trades: List[Trade] = []
        
        # Métricas
        self.metrics = BotMetrics()
        
        # Configuración
        self.risk_per_trade = 0.02  # 2% del capital por trade
        self.max_positions = 1  # Máximo de posiciones simultáneas
        
        print(f"  [TradingBot] Inicializado: {strategy.value} para {symbol}")
        print(f"  [TradingBot] Capital: ${initial_capital:,.2f}")
    
    def process_state(self, state: TimeSeriesState) -> Optional[Trade]:
        """
        Procesar estado de mercado y generar señal.
        
        Args:
            state: Estado actual de serie temporal
        
        Returns:
            Trade si se ejecuta operación, None si no
        """
        # Actualizar régimen
        self.current_regime = state.current_regime
        
        # Buscar patrones coincidentes
        matches = self.pattern_db.match_patterns(state, self.current_regime)
        
        if not matches:
            return None
        
        # Seleccionar mejor patrón (mayor confianza)
        best_pattern = matches[0]
        
        # Verificar si podemos operar
        if self.position is not None and self.max_positions <= 1:
            # Ya tenemos posición, verificar si cerrar
            return self._manage_existing_position(state)
        
        # Generar señal
        trade = self._generate_signal(best_pattern, state)
        
        if trade:
            self.open_trades.append(trade)
            print(f"  [TradingBot] 🎯 Señal: {trade.order_type.value} @ ${trade.price:.6f}")
        
        return trade
    
    def _generate_signal(self, pattern: MarketStoredPattern,
                        state: TimeSeriesState) -> Optional[Trade]:
        """
        Generar señal de trading desde patrón.

        QC Especificación v1.0 + Manual Oficial v5.0.2-R (Vol. III, Sec. 2.2):
        - MARKET_NEUTRAL opera en régimen LATERAL
        - Triggers con tolerancia 1% para range trading (S05)
        - E(pt) > 0.45 para generar señal (S06)
        """
        # S06: Umbral de E(pt) para operar (Manual Oficial v5.0.2-R)
        if pattern.confidence < 0.45:
            return None  # E(pt) muy baja, no operar
        
        # Verificar estrategia vs señal
        if self.strategy == BotStrategy.BULL and pattern.entry_signal == 'sell':
            return None  # Estrategia alcista no vende

        if self.strategy == BotStrategy.BEAR and pattern.entry_signal == 'buy':
            return None  # Estrategia bajista no compra

        # MARKET_NEUTRAL opera en LATERAL con range_buy_low y range_sell_high
        if self.strategy == BotStrategy.MARKET_NEUTRAL:
            if pattern.regime != MarketRegime.LATERAL:
                return None  # MARKET_NEUTRAL solo opera en LATERAL
            if pattern.entry_signal not in ['buy', 'sell']:
                return None
        
        current_price = state.closes[-1]
        timestamp = int(state.timestamps[-1])

        # Calcular tamaño de posición
        position_size = self._calculate_position_size(
            current_price,
            pattern.stop_loss_pct,
            pattern.confidence,  # 1C.1: Pass confidence for dynamic sizing
            pattern.regime.value  # 1C.8: Pass regime for regime-based sizing
        )
        
        if position_size <= 0:
            return None
        
        # Crear trade
        trade = Trade(
            timestamp=timestamp,
            symbol=self.symbol,
            order_type=OrderType(pattern.entry_signal),
            price=current_price,
            amount=position_size,
            regime=self.current_regime,
            pattern_used=pattern.pattern_type,
            stop_loss=pattern.stop_loss_pct,
            take_profit=pattern.take_profit_pct
        )
        
        # Actualizar posición
        if pattern.entry_signal in ['buy', 'sell']:
            self.position = BotPosition(
                symbol=self.symbol,
                amount=position_size if pattern.entry_signal == 'buy' else -position_size,
                entry_price=current_price,
                entry_timestamp=timestamp,
                current_price=current_price,
                stop_loss_pct=pattern.stop_loss_pct,
                take_profit_pct=pattern.take_profit_pct,
                bars_held=0
            )

            # Reducir capital (10% margen)
            self.capital -= current_price * position_size * 0.1
        
        return trade
    
    def _manage_existing_position(self, state: TimeSeriesState) -> Optional[Trade]:
        """
        Gestionar posición existente (stop loss / take profit / time exit).
        
        FIX 1B.7: Corregir lógica de stop-loss/take-profit que estaba bloqueando trades.
        - Usar stop_loss_pct y take_profit_pct de la posición
        - Incrementar bars_held para Triple Barrier
        - Comparar PnL% real contra umbrales correctos
        """
        if self.position is None:
            return None

        current_price = state.closes[-1]
        timestamp = int(state.timestamps[-1])

        # Actualizar precio
        self.position.update_price(current_price)
        
        # Incrementar barras mantenidas (Triple Barrier)
        self.position.bars_held += 1

        # Obtener PnL porcentual real (ya está en porcentaje, ej: 2.5 = 2.5%)
        pnl_pct = self.position.unrealized_pnl_pct

        # =========================================================================
        # FIX 1B.7: Usar umbrales correctos de stop-loss y take-profit
        # =========================================================================
        stop_loss_pct = self.position.stop_loss_pct
        take_profit_pct = self.position.take_profit_pct
        bars_held = self.position.bars_held

        # Verificar stop loss (pérdida máxima alcanzada)
        if pnl_pct <= -stop_loss_pct * 100:
            print(f"  [TradingBot] 🛑 STOP LOSS: PnL={pnl_pct:.2f}% <= {-stop_loss_pct*100:.2f}%")
            return self._close_position(current_price, timestamp, "stop_loss")

        # Verificar take profit (ganancia objetivo alcanzada)
        if pnl_pct >= take_profit_pct * 100:
            print(f"  [TradingBot] 🎯 TAKE PROFIT: PnL={pnl_pct:.2f}% >= {take_profit_pct*100:.2f}%")
            return self._close_position(current_price, timestamp, "take_profit")

        # Verificar time exit (Triple Barrier - tiempo máximo)
        max_holding_bars = getattr(self, 'max_holding_bars', 50)
        if bars_held >= max_holding_bars:
            print(f"  [TradingBot] ⏰ TIME EXIT: {bars_held} >= {max_holding_bars} barras")
            return self._close_position(current_price, timestamp, "time_exit")

        return None
    
    def _close_position(self, price: float, timestamp: int, reason: str) -> Trade:
        """Cerrar posición."""
        if self.position is None:
            raise ValueError("No hay posición abierta")
        
        # Determinar orden opuesta
        if self.position.amount > 0:
            order_type = OrderType.SELL
        else:
            order_type = OrderType.BUY
        
        # Calcular PnL
        pnl = self.position.unrealized_pnl
        pnl_pct = self.position.unrealized_pnl_pct
        
        # Crear trade de cierre
        close_trade = Trade(
            timestamp=timestamp,
            symbol=self.symbol,
            order_type=order_type,
            price=price,
            amount=abs(self.position.amount),
            regime=self.current_regime,
            pattern_used=f"close_{reason}",
            stop_loss=0,
            take_profit=0
        )
        
        # Cerrar trade original
        if self.open_trades:
            original_trade = self.open_trades[-1]
            original_trade.close(price, timestamp)
            self.closed_trades.append(original_trade)
            
            # Actualizar métricas
            self.metrics.update(original_trade)
            
            print(f"  [TradingBot] 💰 {reason}: PnL={original_trade.pnl_pct:.2f}%")
        
        # Liberar posición
        self.capital += price * abs(self.position.amount) * 0.1
        self.position = None
        
        return close_trade
    
    def _calculate_position_size(self, price: float, stop_loss_pct: float,
                                 pattern_confidence: float = 0.5,
                                 regime: str = 'LATERAL') -> float:
        """
        Calcular tamaño de posición según gestión de riesgo.

        1C.1: Confidence-based position sizing (1-3%)
        - High confidence (E(pt)>0.7): 3% position
        - Medium confidence (0.5-0.7): 2% position
        - Low confidence (<0.5): 1% position

        1C.8: Regime-based position sizing adjustment
        - BEAR: 0.75x (reduce exposure during calibration)
        - LATERAL: 1.0x (maintain)
        - BULL: 1.0x (maintain)

        1C.9: Confidence-based sizing refinement (more granular)
        - E(pt) >= 0.70: 1.25x multiplier (high conviction)
        - E(pt) >= 0.60: 1.0x multiplier (medium)
        - E(pt) >= 0.55: 0.75x multiplier (low confidence, new threshold)
        - E(pt) < 0.55: 0.5x multiplier (very low, minimal exposure)

        1D.2: Premium tier for very high confidence (>=0.80)
        - E(pt) >= 0.80: Premium tier (3.0% position, 1.5x multiplier)
        - E(pt) >= 0.70: High confidence (2.5% position, 1.25x multiplier)
        - E(pt) >= 0.60: Medium confidence (2.0% position, 1.0x multiplier)
        - E(pt) < 0.60: Low confidence (1.5% position, 0.75x multiplier)

        Args:
            price: Current price
            stop_loss_pct: Stop loss percentage
            pattern_confidence: Pattern confidence E(pt) [0.1-1.0]
            regime: Market regime ('BULL', 'BEAR', 'LATERAL')

        Returns:
            Position size in units
        """
        # 1D.3: Premium tier adjusted for drawdown control (was 3.0% → 2.0% base)
        if pattern_confidence >= 0.80:
            base_position_pct = 0.02  # 2.0% base (was 3.0%)
            confidence_multiplier = 1.5  # 3.0% total (was 4.5%)
        elif pattern_confidence >= 0.70:
            base_position_pct = 0.025  # 2.5% for high confidence
            confidence_multiplier = 1.25
        elif pattern_confidence >= 0.60:
            base_position_pct = 0.02  # 2.0% for medium confidence
            confidence_multiplier = 1.0
        else:
            base_position_pct = 0.015  # 1.5% for low confidence
            confidence_multiplier = 0.75

        # 1C.8: Regime-based adjustment
        regime_multiplier = 1.0  # Default
        if regime == 'BEAR':
            regime_multiplier = 0.75  # Reduce BEAR exposure (calibration phase)
        elif regime == 'LATERAL':
            regime_multiplier = 1.0  # Maintain
        elif regime == 'BULL':
            regime_multiplier = 1.0  # Maintain

        # Combine multipliers
        position_pct = base_position_pct * confidence_multiplier * regime_multiplier

        # 1D.4: Hard cap validation (MAX_POSITION_PCT = 3.0%)
        MAX_POSITION_PCT = 0.03  # Hard cap at 3.0%
        position_pct = min(position_pct, MAX_POSITION_PCT)

        risk_amount = self.capital * position_pct

        if stop_loss_pct <= 0:
            stop_loss_pct = 0.02  # Default 2%

        # Position size = risk / stop_loss
        position_size = risk_amount / (price * stop_loss_pct)

        print(f"  [TradingBot] Position sizing: confidence={pattern_confidence:.2f}, regime={regime} → {position_pct*100:.1f}% risk (base={base_position_pct*100:.1f}%, conf_mult={confidence_multiplier:.2f}, reg_mult={regime_multiplier:.2f})")

        return max(0.001, position_size)  # Minimum 0.001
    
    def get_metrics(self) -> BotMetrics:
        """Obtener métricas de rendimiento."""
        return self.metrics
    
    def __repr__(self):
        return f"TradingBot({self.strategy.value}, {self.symbol}, capital=${self.capital:,.2f})"


# ============================================================================
# BACKTESTER
# ============================================================================

class Backtester:
    """
    Backtester para estrategias de trading MSE.
    
    ETAPA 6: Validar con datos históricos
    """
    
    def __init__(self, pattern_db: Optional[MarketPatternDatabase] = None):
        self.pattern_db = pattern_db or MarketPatternDatabase()
        self.results: List[Dict[str, Any]] = []
    
    def run(self, state: TimeSeriesState, strategy: BotStrategy,
            initial_capital: float = 10000.0) -> Dict[str, Any]:
        """
        Ejecutar backtest.
        
        Args:
            state: Estado con datos históricos
            strategy: Estrategia a testear
            initial_capital: Capital inicial
        
        Returns:
            Dict con resultados del backtest
        """
        # Crear bot
        bot = TradingBot(
            strategy=strategy,
            symbol=state.symbol,
            initial_capital=initial_capital,
            pattern_db=self.pattern_db
        )
        
        # Procesar cada timestamp
        for i in range(20, len(state.market_states)):  # Skip initial for indicators
            # Crear estado parcial
            partial_state = TimeSeriesState(
                data=state.market_states[:i+1],
                symbol=state.symbol,
                window_size=20
            )
            
            # Procesar
            bot.process_state(partial_state)
        
        # Obtener resultados
        metrics = bot.get_metrics()
        
        results = {
            'strategy': strategy.value,
            'symbol': state.symbol,
            'initial_capital': initial_capital,
            'final_capital': bot.capital,
            'total_return': (bot.capital - initial_capital) / initial_capital * 100,
            'total_trades': metrics.total_trades,
            'win_rate': metrics.win_rate * 100,
            'total_pnl': metrics.total_pnl,
            'regime_stats': metrics.regime_stats
        }
        
        self.results.append(results)
        
        return results


# ============================================================================
# TRADING BOT AUTONOMOUS (N3 - Auto-selección de estrategia)
# ============================================================================

class TradingBotAutonomous(TradingBot):
    """
    Trading Bot con auto-selección de estrategia (N3 autonomía).
    
    Formalización (MSE-V Sec. IV.2):
      select_strategy(state, patterns, regime, Φ) → Strategy
    
    Lógica:
      1. Calcular score por estrategia:
         score_BULL = Σ E(pt) para pt ∈ patterns si pt.regime == BULL
         score_BEAR = Σ E(pt) para pt ∈ patterns si pt.regime == BEAR
         score_LATERAL = Σ E(pt) para pt ∈ patterns si pt.regime == LATERAL
         score_NEUTRAL = 0.50  # Base por defecto
      
      2. Aplicar softmax con temperatura τ (de Φ):
         probs = softmax([scores] / τ)
      
      3. Muestrear estrategia:
         strategy = choice([BULL, BEAR, LATERAL, NEUTRAL], p=probs)
      
      4. Registrar para REINFORCE:
         log_prob = log(probs[strategy])
    
    generate_signal(state, strategy, patterns) → Signal:
      SI strategy == BULL:
        SI ∃ pt con pt.regime == BULL ∧ pt.E_pt > 0.60:
          signal = BUY
        SINO: signal = HOLD
      
      SI strategy == LATERAL:
        SI ∃ pt con pt.regime == LATERAL ∧ pt.E_pt > 0.55:
          signal = RANGE_TRADE
        SINO: signal = HOLD
    
    Criterio de Éxito:
      - MSE selecciona estrategia sin input humano
      - Win rate ≥55% en backtest
    """
    
    def __init__(self, symbol: str, initial_capital: float = 10000.0,
                 pattern_db: Optional[MarketPatternDatabase] = None,
                 meta_learner: Optional[TradingMetaLearner] = None,
                 **kwargs):
        """
        Inicializar bot autónomo con ajustes Fase 1.

        Args:
            symbol: Símbolo del activo
            initial_capital: Capital inicial
            pattern_db: Base de datos de patrones
            meta_learner: Meta learner para REINFORCE
            kwargs: Parámetros adicionales (S09, S13, L04)
        """
        # Inicializar con estrategia por defecto (se actualizará autónomamente)
        super().__init__(
            strategy=BotStrategy.MARKET_NEUTRAL,
            symbol=symbol,
            initial_capital=initial_capital,
            pattern_db=pattern_db
        )

        # Meta learner para auto-selección
        self.meta_learner = meta_learner or TradingMetaLearner(pattern_db=pattern_db)

        # Meta-parámetros (heredados del padre + acceso directo)
        self.meta_params = self.meta_learner.meta_params

        # ========================================================================
        # FASE 1: AJUSTES DE UMBRALES Y TRIPLE BARRERA
        # ========================================================================

        # 1B.16: Position sizing ULTRA reducido (3% → 2%) para drawdown <15%
        self.position_size_pct = kwargs.get('position_size_pct', 0.02)  # 1B.16: 0.03 → 0.02 (2% ultra conservador)

        # S09: Range tolerance aumentado para más operaciones (1% → 2.5%)
        self.range_tolerance = kwargs.get('range_tolerance', 0.025)  # ANTES: 0.01

        # S13: Triple Barrera - Tiempo máximo de posición
        self.max_holding_bars = kwargs.get('max_holding_bars', 200)  # 1D.6 FIX: 50 → 200 (4x más tiempo para patrones)

        # 1C.9: Trigger de E(pt) para Win Rate Optimization (filter low-quality patterns)
        # 1C.10: Balance quality vs quantity (0.55 → 0.50)
        # 1D.2: Historical best from 1B.14-1B.16 (0.50 → 0.40)
        self.e_pt_trigger = kwargs.get('e_pt_trigger', 0.40)  # 1D.2: 0.50 → 0.40 (historical best from 1B.14-1B.16)

        # 1C.5: Triple Barrera - Stop loss REVERTIDO (1.25% → 1.5%) por volatilidad crypto
        self.stop_loss_pct = kwargs.get('stop_loss_pct', 0.015)  # 1C.5: 0.0125 → 0.015 (1.5% revert to 1C.3)

        # R01-R03: Validador de regímenes (1B.6: thresholds más permisivos)
        self.regime_validator = RegimeValidator(
            z_score_threshold=kwargs.get('z_score_threshold', 0.08),  # 1B.6: 0.02 → 0.08
            volatility_threshold=kwargs.get('volatility_threshold', 0.08),  # 1B.6: 0.03 → 0.08
            trend_window=kwargs.get('trend_window', 50)
        )

        # ========================================================================
        # 1C.8: REGIME-SPECIFIC PARAMETERS (Single TP 5% - Easier to Reach)
        # ========================================================================
        # 1C.8: TP/SL Ratio 4:1 → 2:1 (More realistic for crypto volatility)
        # Root cause 1C.7: TP 10-12% too ambitious, few wins captured, time exits dominate
        # 1C.8: TP=5%, SL=2.5% (ratio 2:1) - More frequent wins, better Sharpe
        # BULL: TP=5%, SL=2.5% (ratio 2.0) - Easier to capture wins
        # BEAR: TP=5%, SL=2.5% (ratio 2.0) - Easier to capture wins
        # LATERAL: TP=5%, SL=2.5% (ratio 2.0) - Balanced for range trading

        # ========================================================================
        # 1C.11: REVERT BEAR TP TO 5% (BEAR TP 3% → 5% - Counter-Trend Fix)
        # ========================================================================
        # Root cause 1C.10: Win rate 45.28% DEGRADED from 1C.9's 49.83%
        # Diagnosis: TP 3% TOO TIGHT for BEAR (counter-trend) - NEOJPY lost all trades
        # Solution: Revert BEAR TP to 5% for better win rate
        # BULL: TP=5%, SL=2.5% (ratio 2.0) - Maintain (excellent at 65.0%)
        # BEAR: TP=5%, SL=2.5% (ratio 2.0) - Revert (3% failed at 0.0%)
        # LATERAL: TP=3%, SL=2.5% (ratio 1.2) - Maintain (investigate separately)

        self.regime_tp_sl = {
            'BULL': {'tp': 0.05, 'sl': 0.025},    # 1C.11: Maintain 5% (excellent)
            'BEAR': {'tp': 0.05, 'sl': 0.025},    # 1C.11: 3% → 5% (REVERT - 3% failed)
            'LATERAL': {'tp': 0.03, 'sl': 0.025}  # 1C.11: Maintain 3% (working)
        }

        # Estado actual
        self.current_strategy: Optional[BotStrategy] = None
        self.current_log_prob: Optional[torch.Tensor] = None

        # Tracking de posiciones para Triple Barrera
        self.position_bars: Dict[str, int] = {}  # trade_id → barras_held

    def get_regime_parameters(self, regime: str) -> Dict[str, float]:
        """
        1C.1: Obtener parámetros TP/SL específicos por régimen.
        
        Args:
            regime: Régimen actual ('BULL', 'BEAR', 'LATERAL')

        Returns:
            Dict con take_profit y stop_loss para el régimen
        """
        return self.regime_tp_sl.get(regime, self.regime_tp_sl['LATERAL'])

    def _boost_crystallized_for_regime(self, patterns: List[MarketStoredPattern],
                                        current_regime: str) -> List[MarketStoredPattern]:
        """
        1D.2: Boost confidence of crystallized patterns that performed well in current regime.
        
        Rationale:
        - Patterns that worked in similar conditions likely to work again
        - Temporary boost (not persisted) for selection only
        - Reverted after trade to avoid inflation
        
        Args:
            patterns: List of patterns to evaluate
            current_regime: Current market regime
            
        Returns:
            List of patterns with temporary confidence boosts applied
        """
        import copy
        boosted_patterns = []
        
        for pattern in patterns:
            if pattern.crystallized and pattern.last_used_regime == current_regime:
                # Check historical performance in this regime
                historical_wr = pattern.performance_by_regime.get(current_regime, 0.5)
                
                if historical_wr > 0.55:  # Good performance in this regime
                    # Create temporary copy with boosted confidence
                    boosted = copy.deepcopy(pattern)
                    boosted.confidence *= 1.1  # 10% boost
                    boosted_patterns.append(boosted)
                else:
                    boosted_patterns.append(pattern)
            else:
                boosted_patterns.append(pattern)
        
        return boosted_patterns

    def select_strategy(self, state: TimeSeriesState) -> Tuple[BotStrategy, torch.Tensor]:
        """
        Seleccionar estrategia autónomamente vía softmax.
        
        1D.2: Apply crystallized pattern boost for regime-specific reuse.

        Returns:
            Tuple[BotStrategy, torch.Tensor]: Estrategia, log_prob
        """
        patterns = self.pattern_db.match_patterns(state)
        regime = state.current_regime.value

        # 1D.2: Boost crystallized patterns that performed well in current regime
        boosted_patterns = self._boost_crystallized_for_regime(patterns, regime)

        # Usar meta learner para selección (with boosted patterns)
        strategy_str, log_prob = self.meta_learner.select_strategy(
            state_features={},
            regime=regime,
            patterns=boosted_patterns
        )

        # Convertir a BotStrategy
        strategy_map = {
            'BULL': BotStrategy.BULL,
            'BEAR': BotStrategy.BEAR,
            'LATERAL': BotStrategy.MARKET_NEUTRAL,
            'MARKET_NEUTRAL': BotStrategy.MARKET_NEUTRAL
        }
        strategy = strategy_map.get(strategy_str, BotStrategy.MARKET_NEUTRAL)

        # Actualizar estado
        self.current_strategy = strategy
        self.current_log_prob = log_prob
        self.current_regime = regime
        self.current_patterns = [p.id for p in patterns]  # Store pattern IDs for episode recording

        return strategy, log_prob
    
    def process_state(self, state: TimeSeriesState) -> Optional[Trade]:
        """
        Procesar estado con auto-selección de estrategia.

        Args:
            state: Estado actual

        Returns:
            Trade si se ejecuta operación
        """
        # 1. Seleccionar estrategia autónomamente (N3)
        strategy, log_prob = self.select_strategy(state)

        # 2. Actualizar estrategia del bot padre
        self.strategy = strategy

        # 3. Procesar con estrategia seleccionada
        trade = super().process_state(state)

        # NOTA: record_episode() se llama en _close_position() cuando tenemos PnL real
        # FIX: Antes se llamaba aquí con pnl=0 porque trade.is_closed era False

        return trade

    def check_exit_conditions(self, position: BotPosition, current_state: TimeSeriesState,
                             bars_held: int) -> Tuple[str, int]:
        """
        S13: Triple Barrera (López de Prado Cap. 3)
        3 condiciones de salida: TP, SL, o Tiempo Máximo

        FIX 1B.7: Usar porcentajes correctamente para TP/SL

        Args:
            position: Posición actual
            current_state: Estado actual del mercado
            bars_held: Barras mantenidas la posición

        Returns:
            Tuple[str, int]: Tipo de salida ('TP_HIT', 'SL_HIT', 'TIME_EXIT', 'HOLD'), barras_held
        """
        current_price = current_state.closes[-1]
        
        # Calcular PnL porcentual actual
        pnl_pct = position.unrealized_pnl_pct

        # Barrera 1: Take Profit (usar porcentaje)
        if pnl_pct >= position.take_profit_pct * 100:
            print(f"[Triple Barrera] 🎯 TP HIT: PnL={pnl_pct:.2f}% >= {position.take_profit_pct*100:.2f}%")
            return 'TP_HIT', bars_held

        # Barrera 2: Stop Loss (usar porcentaje)
        if pnl_pct <= -position.stop_loss_pct * 100:
            print(f"[Triple Barrera] 🛑 SL HIT: PnL={pnl_pct:.2f}% <= {-position.stop_loss_pct*100:.2f}%")
            return 'SL_HIT', bars_held

        # Barrera 3: Tiempo Máximo (NUEVO) - 1D.7: Dinámico basado en confianza y volatilidad
        max_bars = self.calculate_dynamic_max_holding_bars()
        if bars_held >= max_bars:
            print(f"[Triple Barrera] ⏰ TIME EXIT DINÁMICO: {bars_held} >= {max_bars} barras (conf={self.get_current_pattern_confidence():.2f}, vol={self.get_current_volatility():.2%})")
            return 'TIME_EXIT', bars_held

        return 'HOLD', bars_held

    def calculate_dynamic_max_holding_bars(self) -> int:
        """
        1D.7 FIX: Calcular tiempo máximo de posición dinámicamente.
        
        Fórmula: base * confidence_multiplier * volatility_multiplier
        
        Returns:
            int: Barras máximas dinámicas
        """
        # Base por régimen
        base = self.max_holding_bars
        
        # Multiplicador por confianza del patrón actual
        confidence = self.get_current_pattern_confidence()
        if confidence >= 0.90:
            confidence_mult = 1.5  # Alta confianza: más tiempo
        elif confidence >= 0.70:
            confidence_mult = 1.0  # Confianza media: tiempo normal
        else:
            confidence_mult = 0.7  # Baja confianza: menos tiempo
        
        # Multiplicador por volatilidad
        volatility = self.get_current_volatility()
        if volatility > 0.05:
            vol_mult = 0.7  # Alta volatilidad: menos tiempo (más riesgo)
        elif volatility > 0.02:
            vol_mult = 1.0  # Volatilidad normal
        else:
            vol_mult = 1.2  # Baja volatilidad: más tiempo
        
        return int(base * confidence_mult * vol_mult)

    def get_current_pattern_confidence(self) -> float:
        """Obtener confianza del patrón actual en uso."""
        if hasattr(self, 'current_patterns') and self.current_patterns and len(self.current_patterns) > 0:
            # Asumir que el primer patrón es el principal
            pattern = self.current_patterns[0]
            if hasattr(pattern, 'confidence'):
                return pattern.confidence
        return 0.50  # Default si no hay patrón

    def get_current_volatility(self) -> float:
        """Obtener volatilidad actual del mercado."""
        if hasattr(self, 'state') and self.state and hasattr(self.state, 'volatility'):
            return self.state.volatility
        return 0.03  # Default 3% volatilidad
    
    def should_operate_pattern(self, pattern: Any, regime: MarketRegime) -> bool:
        """
        L04: Verificar si patrón tiene E(pt) suficiente para operar.
        Reducido de 0.55 a 0.45 para permitir operación durante aprendizaje.
        
        Args:
            pattern: Patrón a verificar
            regime: Régimen actual
        
        Returns:
            bool: True si debe operar
        """
        # L04: Trigger reducido de 0.55 → 0.45
        if pattern.confidence >= self.e_pt_trigger:
            return True
        
        # Patrones cristalizados siempre operan (E > 0.95)
        if hasattr(pattern, 'crystallized') and pattern.crystallized:
            return True
        
        return False
    
    def update_meta_policy(self, min_episodes: int = 3):
        """
        Actualizar política de estrategia vía REINFORCE.

        Args:
            min_episodes: Minimum episodes required before updating (default: 3)
                         This prevents updates with insufficient data.

        Returns:
            Gradients if update was performed, empty dict otherwise.
        """
        # Check if we have enough episodes
        if len(self.meta_learner.log_probs_history) < min_episodes:
            print(f"[MetaLearner DEBUG] update_meta_policy: Skipping update, only {len(self.meta_learner.log_probs_history)} episodes (need {min_episodes})")
            return {}

        print(f"[MetaLearner DEBUG] update_meta_policy: Updating with {len(self.meta_learner.log_probs_history)} episodes")
        gradients = self.meta_learner.update_strategy_policy(self.meta_params)
        return gradients

    def update_pattern_effectiveness(self, pattern_id: str, pnl_pct: float,
                                    success_threshold: float = 0.0):
        """
        Actualizar E(pt) tras resultado con REINFORCE proporcional (1B.8).

        Args:
            pattern_id: ID del patrón
            pnl_pct: PnL porcentual en decimal (ej: 0.05 = 5%)
            success_threshold: Umbral para considerar éxito (default: 0.0)
        """
        self.meta_learner.update_pattern_effectiveness(
            pattern_id, pnl_pct, success_threshold, self.meta_params
        )

    def _close_position(self, price: float, timestamp: int, reason: str) -> Trade:
        """
        Cerrar posición y actualizar E(pt) con REINFORCE proporcional (1B.8).

        Args:
            price: Precio de cierre
            timestamp: Timestamp de cierre
            reason: Razón del cierre ('stop_loss', 'take_profit', 'time_exit')

        Returns:
            Trade de cierre
        """
        # Llamar al método padre para cerrar
        close_trade = super()._close_position(price, timestamp, reason)

        # 1B.8: Actualizar E(pt) con pnl_pct proporcional
        if len(self.closed_trades) > 0:
            # Obtener el trade cerrado más reciente
            last_trade = self.closed_trades[-1]

            # Convertir pnl_pct de porcentaje a decimal (ej: 5.2% → 0.052)
            pnl_pct_decimal = last_trade.pnl_pct / 100.0 if last_trade.pnl_pct else 0.0

            # Actualizar E(pt) del patrón usado
            if hasattr(last_trade, 'pattern_used') and last_trade.pattern_used:
                self.update_pattern_effectiveness(
                    pattern_id=last_trade.pattern_used,
                    pnl_pct=pnl_pct_decimal,
                    success_threshold=0.0
                )

        # REINFORCE: Registrar episodio con PnL REAL (FIX: antes se registraba con pnl=0)
        # Usar información almacenada cuando se abrió la posición
        if hasattr(self, 'current_strategy') and hasattr(self, 'current_log_prob') and len(self.closed_trades) > 0:
            strategy_value = self.current_strategy.value if hasattr(self.current_strategy, 'value') else str(self.current_strategy)
            log_prob_value = self.current_log_prob.item() if hasattr(self.current_log_prob, 'item') else float(self.current_log_prob)
            regime_value = getattr(self, 'current_regime', 'unknown')
            patterns_used = getattr(self, 'current_patterns', [])

            # Usar PnL del trade cerrado (último en closed_trades)
            last_trade = self.closed_trades[-1]
            actual_pnl = last_trade.pnl_pct if last_trade else 0.0

            self.meta_learner.record_episode(
                strategy=strategy_value,
                log_prob=self.current_log_prob,
                regime=regime_value,
                patterns_used=patterns_used,
                pnl=actual_pnl
            )

        return close_trade
    
    def get_autonomy_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas de autonomía."""
        meta_stats = self.meta_learner.get_stats()
        
        return {
            'current_strategy': self.current_strategy.value if self.current_strategy else None,
            'meta_learner': meta_stats,
            'total_trades': len(self.open_trades) + len(self.closed_trades),
            'win_rate': self.metrics.win_rate
        }


# ============================================================================
# TESTS
# ============================================================================

if __name__ == "__main__":
    print("="*60)
    print("TEST: Trading Bot - MSE v5.0.2-R ETAPA 6")
    print("="*60)
    
    # Crear datos sintéticos
    from src.python.market.axioms import MarketState
    
    print("\nTest 1: Crear bot alcista")
    synthetic_states = [
        MarketState(
            timestamp=i*60,
            open=100+i*0.5, high=101+i*0.5, low=99+i*0.5, close=100.5+i*0.5,
            volume=1.0, symbol="TEST/BTC",
            regime=MarketRegime.BULL if i > 10 else MarketRegime.LATERAL
        )
        for i in range(50)
    ]
    
    state = TimeSeriesState(data=synthetic_states, symbol="TEST/BTC", window_size=20)
    
    bot = TradingBot(strategy=BotStrategy.BULL, symbol="TEST/BTC", initial_capital=10000)
    print(f"  Bot: {bot}")
    print("  ✓ PASSED")
    
    print("\nTest 2: Procesar estado")
    trade = bot.process_state(state)
    print(f"  Trade: {trade}")
    print("  ✓ PASSED")
    
    print("\nTest 3: Backtester")
    backtester = Backtester()
    results = backtester.run(state, BotStrategy.BULL, initial_capital=10000)
    print(f"  Return: {results['total_return']:.2f}%")
    print(f"  Trades: {results['total_trades']}")
    print(f"  Win Rate: {results['win_rate']:.1f}%")
    print("  ✓ PASSED")
    
    print("\n" + "="*60)
    print("TESTS DE TRADING BOT PASSED")
    print("="*60)
