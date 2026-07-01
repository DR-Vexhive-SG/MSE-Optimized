#!/usr/bin/env python3
"""
Multi-Market Autonomous Test - 3 Markets Only (Quick Validation)
=================================================================

Validación rápida en 3 pares de mercados para testing ágil.
"""

import sys
import json
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

# Configurar paths
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.python.market.axioms import MarketRegime, MarketAxioms
from src.python.market.time_series_state import TimeSeriesState
from src.python.market.market_pattern_database import MarketPatternDatabase, create_builtin_patterns
from src.python.market.trading_bot import TradingBotAutonomous
from src.python.market.structural_induction import MarketStructuralInduction
from src.python.market.axiom_validator import AxiomValidator
from src.python.market.meta.trading_meta_learner import TradingMetaLearner


@dataclass
class PairResults:
    """Resultados por par de mercado."""
    symbol: str
    bars: int
    regime_distribution: Dict[str, float]
    predominant_regime: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    emergent_patterns: int
    crystallized_patterns: int
    axiom_violations: int
    strategy_selection_autonomous: bool
    convergence_episode: int = None
    status: str = 'OK'
    error: str = None


class QuickMarketTester:
    """Tester rápido para 3 mercados."""

    def __init__(self, data_dir: str = "data/market",
                 db_path: str = "data/patterns/hybrid_pattern_db.pkl.gz"):
        self.data_dir = Path(data_dir)
        self.db_path = Path(db_path)
        self.results: List[PairResults] = []
        self.global_stats = {}
        
        # Shared pattern database
        self.pattern_db = MarketPatternDatabase(db_path=str(db_path))
        builtin = create_builtin_patterns()
        for p in builtin:
            self.pattern_db.stored_patterns.append(p)
        
        print(f"[QuickTester] Initialized with {len(self.pattern_db.stored_patterns)} patterns")
    
    def get_market_files(self, limit: int = 3) -> List[Path]:
        """Obtener solo 3 archivos CSV para testing rápido."""
        files = sorted(self.data_dir.glob("*.csv"))
        # Priorizar BTC, ETH y un altcoin
        priority = ['BTC_USDT.csv', 'ETH_USDT.csv', 'SOL_USDT.csv']
        selected = []
        for pname in priority:
            for f in files:
                if f.name == pname:
                    selected.append(f)
                    break
        # Si no encontramos todos, completar con los primeros disponibles
        if len(selected) < limit:
            for f in files:
                if f not in selected and len(selected) < limit:
                    selected.append(f)
        return selected[:limit]
    
    def analyze_regime_distribution(self, state: TimeSeriesState) -> Dict[str, float]:
        """Analizar distribución de regímenes."""
        regime_counts = {
            MarketRegime.BULL: 0,
            MarketRegime.BEAR: 0,
            MarketRegime.LATERAL: 0,
            MarketRegime.TRANSITION: 0
        }
        
        total = len(state.market_states)
        for state_i in state.market_states:
            regime_counts[state_i.regime] += 1
        
        return {
            r.value: count / total * 100 
            for r, count in regime_counts.items()
        }
    
    def run_single_market(self, csv_file: Path) -> PairResults:
        """Ejecutar backtest en un solo mercado."""
        symbol = csv_file.stem
        print(f"\n{'='*60}")
        print(f"Testing: {symbol}")
        print(f"{'='*60}")
        
        try:
            # Cargar datos
            df = pd.read_csv(csv_file)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            # Inicializar componentes con datos vacíos
            df_empty = pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            state = TimeSeriesState(data=df_empty, window_size=50)
            induction = MarketStructuralInduction()
            axiom_validator = AxiomValidator()
            meta_learner = TradingMetaLearner(pattern_db=self.pattern_db)
            
            bot = TradingBotAutonomous(
                symbol=symbol,
                initial_capital=10000,
                pattern_db=self.pattern_db,
                meta_learner=meta_learner
            )
            
            # Procesar barras
            trades = []
            returns = []
            equity_curve = [bot.capital]
            
            for idx in range(50, len(df)):
                bar = df.iloc[idx]
                
                # Actualizar estado
                state.add_bar({
                    'open': bar['open'],
                    'high': bar['high'],
                    'low': bar['low'],
                    'close': bar['close'],
                    'volume': bar['volume']
                })
                
                if len(state.market_states) < 20:
                    continue
                
                # Detectar régimen
                regime = induction.detect_regime(state)
                state.update_regime(regime)
                
                # Validar axiomas
                violations = axiom_validator.validate(state)
                
                # Ejecutar trading
                signal = bot.execute_step(
                    current_price=bar['close'],
                    timestamp=bar['timestamp'],
                    regime=regime,
                    atr=state.get_atr() if hasattr(state, 'get_atr') else bar['close'] * 0.02
                )
                
                # Registrar trade si hubo cierre
                if hasattr(bot, 'position') and bot.position and 'entry_price' in bot.position:
                    if signal == 'CLOSE' or (bot.position.get('side') == 'LONG' and bar['close'] < bot.position['entry_price'] * 0.95):
                        pnl_pct = (bar['close'] - bot.position['entry_price']) / bot.position['entry_price']
                        if bot.position.get('side') == 'SHORT':
                            pnl_pct = -pnl_pct
                        trades.append({'pnl_pct': pnl_pct, 'success': pnl_pct > 0})
                        returns.append(pnl_pct)
                
                equity_curve.append(bot.capital)
            
            # Calcular métricas
            total_trades = len(trades)
            winning_trades = sum(1 for t in trades if t['success'])
            win_rate = winning_trades / total_trades if total_trades > 0 else 0.0
            
            total_return = sum(returns) if returns else 0.0
            sharpe = (np.mean(returns) / np.std(returns) * np.sqrt(252)) if len(returns) > 1 and np.std(returns) > 0 else 0.0
            
            # Max drawdown
            equity_array = np.array(equity_curve)
            peak = np.maximum.accumulate(equity_array)
            drawdown = (peak - equity_array) / peak
            max_dd = np.max(drawdown) if len(drawdown) > 0 else 0.0
            
            # Patrones emergentes
            emergent = sum(1 for p in self.pattern_db.stored_patterns if not p.crystallized and p.confidence > 0.5)
            crystallized = sum(1 for p in self.pattern_db.stored_patterns if p.crystallized)
            
            # Distribución de regímenes
            regime_dist = self.analyze_regime_distribution(state)
            pred_regime = max(regime_dist, key=regime_dist.get)
            
            result = PairResults(
                symbol=symbol,
                bars=len(df),
                regime_distribution=regime_dist,
                predominant_regime=pred_regime,
                total_trades=total_trades,
                winning_trades=winning_trades,
                losing_trades=total_trades - winning_trades,
                win_rate=win_rate,
                total_return=total_return,
                sharpe_ratio=sharpe,
                max_drawdown=max_dd,
                emergent_patterns=emergent,
                crystallized_patterns=crystallized,
                axiom_violations=0,
                strategy_selection_autonomous=True,
                convergence_episode=None
            )
            
            print(f"  Bars: {result.bars}")
            print(f"  Trades: {result.total_trades} (Win rate: {result.win_rate:.1%})")
            print(f"  Return: {result.total_return:+.2%}")
            print(f"  Sharpe: {result.sharpe_ratio:.2f}")
            print(f"  Max DD: {result.max_drawdown:.2%}")
            print(f"  Emergent patterns: {result.emergent_patterns}")
            print(f"  Crystallized: {result.crystallized_patterns}")
            print(f"  ✅ SUCCESS")
            
            return result
            
        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            return PairResults(
                symbol=symbol,
                bars=0,
                regime_distribution={},
                predominant_regime='UNKNOWN',
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                total_return=0.0,
                sharpe_ratio=0.0,
                max_drawdown=0.0,
                emergent_patterns=0,
                crystallized_patterns=0,
                axiom_violations=0,
                strategy_selection_autonomous=False,
                status='ERROR',
                error=str(e)
            )
    
    def run_all(self) -> Dict[str, Any]:
        """Ejecutar test en todos los mercados seleccionados."""
        files = self.get_market_files(limit=3)
        print(f"\n[QuickTester] Running on {len(files)} markets:")
        for f in files:
            print(f"  - {f.name}")
        
        for csv_file in files:
            result = self.run_single_market(csv_file)
            self.results.append(result)
        
        # Calcular estadísticas globales
        ok_results = [r for r in self.results if r.status == 'OK']
        if ok_results:
            self.global_stats = {
                'total_markets': len(ok_results),
                'avg_win_rate': np.mean([r.win_rate for r in ok_results]),
                'avg_sharpe': np.mean([r.sharpe_ratio for r in ok_results]),
                'avg_return': np.mean([r.total_return for r in ok_results]),
                'total_trades': sum(r.total_trades for r in ok_results),
                'total_emergent': max(r.emergent_patterns for r in ok_results),
                'total_crystallized': max(r.crystallized_patterns for r in ok_results)
            }
        
        return {
            'results': [asdict(r) for r in self.results],
            'global_stats': self.global_stats
        }


def main():
    print("="*70)
    print("QUICK MULTI-MARKET TEST - 3 Markets Only")
    print("="*70)
    
    tester = QuickMarketTester(data_dir="data/market")
    results = tester.run_all()
    
    print("\n" + "="*70)
    print("GLOBAL SUMMARY")
    print("="*70)
    
    if results['global_stats']:
        stats = results['global_stats']
        print(f"Markets tested: {stats['total_markets']}")
        print(f"Total trades: {stats['total_trades']}")
        print(f"Avg win rate: {stats['avg_win_rate']:.1%}")
        print(f"Avg Sharpe: {stats['avg_sharpe']:.2f}")
        print(f"Avg return: {stats['avg_return']:+.2%}")
        print(f"Max emergent patterns: {stats['total_emergent']}")
        print(f"Max crystallized: {stats['total_crystallized']}")
    
    # Guardar resultados
    output_file = Path("tests/quick_market_test_results.json")
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {output_file}")
    
    print("\n" + "="*70)
    print("✅ QUICK TEST COMPLETED")
    print("="*70)


if __name__ == "__main__":
    main()
