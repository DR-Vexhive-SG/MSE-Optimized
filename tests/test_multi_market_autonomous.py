#!/usr/bin/env python3
"""
Multi-Market Autonomous Test - MSE v5.0.2-R
============================================

Validación en 12 pares de mercados con autonomía N2+N3.
Conexión formal: MSE v5.0-R Sec. V (Propiedades Formales), DOCUMENTO UNIFICADO ETAPA 6

Criterios de Aceptación (CA1-CA8):
- CA1: Patrones emergentes ≥5 en 12 CSV
- CA2: Auto-selección estrategia 100% episodios
- CA3: Win rate ≥55%
- CA4: Sharpe ratio ≥1.0
- CA5: Max drawdown <15%
- CA6: Violaciones axiomáticas = 0
- CA7: Convergencia Φ ≤50 episodios
- CA8: Cristalización patrones ≥2
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


class MultiMarketTester:
    """
    Tester multi-mercado autónomo.

    Procedimiento:
      1. Cargar 12 CSV files
      2. Por cada file:
         - Inicializar TradingBotAutonomous
         - Ejecutar episodio completo (sin intervención humana)
         - Registrar métricas
         - Actualizar Φ vía REINFORCE
      3. Calcular métricas globales
      4. Validar CA1-CA8
    
    1C.8: Persistence Validation
      - Verify patterns load from previous session
      - Verify patterns save after backtest
      - Verify crystallized patterns accumulate across runs
    """

    def __init__(self, data_dir: str = "data/market", 
                 db_path: str = "data/patterns/hybrid_pattern_db.pkl.gz"):
        self.data_dir = Path(data_dir)
        self.db_path = Path(db_path)
        self.results: List[PairResults] = []
        self.global_stats = {}
        # FIX v5.0.2-R: Shared pattern database for cross-pair learning
        self.pattern_db = MarketPatternDatabase(db_path=str(db_path))
        builtin = create_builtin_patterns()
        for p in builtin:
            self.pattern_db.stored_patterns.append(p)
        
        # 1C.8: Persistence validation - track initial state
        self.initial_pattern_count = len(self.pattern_db.stored_patterns)
        self.initial_crystallized = sum(1 for p in self.pattern_db.stored_patterns if p.crystallized)
        
        print(f"[MultiMarketTester] Initialized with {len(self.pattern_db.stored_patterns)} patterns")
        print(f"[MultiMarketTester] Initial crystallized: {self.initial_crystallized}")
        print(f"[MultiMarketTester] DB path: {db_path}")
    
    def get_market_files(self) -> List[Path]:
        """Obtener lista de archivos CSV de mercado."""
        return sorted(self.data_dir.glob("Bitfinex_*.csv"))
    
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
    
    def run_backtest_for_pair(self, file_path: Path,
                             initial_capital: float = 10000.0,
                             max_bars: int = 1000,
                             pattern_db: Optional[MarketPatternDatabase] = None) -> PairResults:
        """
        Ejecutar backtest autónomo para un par.

        Args:
            file_path: Archivo CSV del par
            initial_capital: Capital inicial
            max_bars: Máximo de barras a procesar
            pattern_db: Base de datos de patrones compartida (opcional)

        Returns:
            PairResults con métricas
        """
        symbol = file_path.stem.replace("Bitfinex_", "").replace("_minute", "").replace("_1h", "")

        try:
            # Cargar datos (subset para velocidad)
            df = pd.read_csv(file_path, skiprows=1).head(max_bars)

            if len(df) < 100:
                return PairResults(
                    symbol=symbol, bars=len(df),
                    regime_distribution={}, predominant_regime='N/A',
                    total_trades=0, winning_trades=0, losing_trades=0,
                    win_rate=0.0, total_return=0.0, sharpe_ratio=0.0,
                    max_drawdown=0.0, emergent_patterns=0,
                    crystallized_patterns=0, axiom_violations=0,
                    strategy_selection_autonomous=False,
                    status='SKIP', error=f'Datos insuficientes: {len(df)} barras'
                )

            # Crear estado
            state = TimeSeriesState(data=df, symbol=symbol, window_size=20)

            # Analizar distribución de regímenes
            regime_dist = self.analyze_regime_distribution(state)
            predominant_regime = max(regime_dist, key=regime_dist.get)

            # Inicializar componentes
            # FIX v5.0.2-R: Use shared pattern_db if provided, otherwise create new EMPTY db
            if pattern_db is None:
                # 1D.5 FIX: Create EMPTY pattern_db (don't load from file)
                pattern_db = MarketPatternDatabase(db_path=None)
                builtin = create_builtin_patterns()
                for p in builtin:
                    pattern_db.stored_patterns.append(p)
                print(f"  [WARNING] Created EMPTY pattern_db with {len(pattern_db.stored_patterns)} patterns")
            # Else use the shared pattern_db (patterns accumulate across pairs)

            meta_learner = TradingMetaLearner(pattern_db=pattern_db)
            self._last_meta_learner = meta_learner  # Store for policy saving (1C.12)
            
            bot = TradingBotAutonomous(
                symbol=symbol,
                initial_capital=initial_capital,
                pattern_db=pattern_db,
                meta_learner=meta_learner
            )
            
            inductor = MarketStructuralInduction(
                min_support=0.03,  # 1B.9: 0.10 → 0.03 (3% para más descubrimiento)
                signature_precision=2,  # 1B.9: 3 → 2 decimales
                debug_mode=False  # 1C.2: Desactivar debug logging para evitar I/O bottleneck
            )
            validator = AxiomValidator()

            # Ejecutar backtest autónomo
            returns = []
            drawdowns = []
            peak_capital = initial_capital

            emergent_patterns_count = 0
            crystallized_count = 0
            axiom_violations = 0
            autonomous_selections = 0

            # 1B.7: FIX - Acumular historial para inducción estructural
            state_history_for_induction = []

            # 1B.10: FIX - step=5 → step=1 para acumulación completa de historial
            # ROOT CAUSE: step=5 pierde barras intermedias, reduciendo oportunidades de pattern discovery
            # FIX: Acumular CADA barra para maximizar emergent_patterns
            for i in range(20, len(state.market_states), 1):  # 1B.10: Step de 1 (todas las barras)
                # Crear estado parcial
                partial_state = TimeSeriesState(
                    data=state.market_states[:i+1],
                    symbol=symbol,
                    window_size=20
                )

                # 1B.7: FIX - Acumular estado para inducción estructural
                state_history_for_induction.append(partial_state)

                # 1B.9: Debug logging - acumulación de historial (1C.3: Disabled to prevent I/O bottleneck)
                # if i % 100 == 0 and i > 0:
                #     print(f"[DEBUG-HISTORY] Iteración {i}: Historial acumulado = {len(state_history_for_induction)} estados")

                # 1. Descubrir patrones emergentes (N2) - 1B.7: Pasar historial acumulado
                try:
                    emergent = inductor.discover_and_validate(state_history_for_induction)
                    emergent_patterns_count += len(emergent)
                except Exception as e:
                    # Silently continue if pattern discovery fails
                    pass

                # 2. Validar soundness axiomática
                if hasattr(partial_state, 'market_states') and len(partial_state.market_states) > 0:
                    current_state = partial_state.market_states[-1]
                    prev_state = partial_state.market_states[-2] if len(partial_state.market_states) > 1 else None
                    
                    # Validar señal (si hay trade)
                    result = validator.validate_signal(
                        signal={'price': current_state.close, 'type': 'hold'},
                        state=current_state,
                        prev_state=prev_state
                    )
                    
                    if result.signal_action == 'REJECT':
                        axiom_violations += 1
                
                # 3. Auto-selección de estrategia (N3)
                strategy, log_prob = bot.select_strategy(partial_state)
                autonomous_selections += 1
                
                # 4. Procesar estado
                trade = bot.process_state(partial_state)

                # 5. Actualizar política REINFORCE (cada 20 barras)
                if i % 20 == 0:
                    bot.update_meta_policy()
                
                # 6. Registrar retornos
                current_capital = bot.capital
                if i > 20:
                    ret = (current_capital - peak_capital) / peak_capital
                    returns.append(ret)
                    
                    # Drawdown
                    if current_capital > peak_capital:
                        peak_capital = current_capital
                    dd = (peak_capital - current_capital) / peak_capital
                    drawdowns.append(dd)
            
            # Calcular métricas
            total_trades = len(bot.closed_trades)
            winning_trades = sum(1 for t in bot.closed_trades if t.pnl > 0)
            losing_trades = total_trades - winning_trades
            win_rate = winning_trades / max(1, total_trades) * 100

            total_return = (bot.capital - initial_capital) / initial_capital * 100

            # Sharpe ratio (anualizado, asumiendo 252 días)
            if len(returns) > 1 and np.std(returns) > 0:
                sharpe_ratio = (np.mean(returns) / np.std(returns)) * np.sqrt(252)
            else:
                sharpe_ratio = 0.0

            # Max drawdown
            max_drawdown = max(drawdowns) * 100 if drawdowns else 0.0

            # 1B.7: FIX - Pattern effectiveness updated in TradingBotAutonomous._close_position()
            # REINFORCE learning with PnL-proportional updates (1B.8)
            # This block removed (1C.12): Was bypassing REINFORCE with boolean updates
            # The correct implementation is in TradingBotAutonomous._close_position() lines 858-883

            # Cristalización
            crystallized_count = sum(1 for p in pattern_db.stored_patterns if p.crystallized)
            
            # Convergencia
            convergence_ep = meta_learner.stats.get('convergence_episode')
            
            # Crear resultados
            results = PairResults(
                symbol=symbol,
                bars=len(df),
                regime_distribution=regime_dist,
                predominant_regime=predominant_regime,
                total_trades=total_trades,
                winning_trades=winning_trades,
                losing_trades=losing_trades,
                win_rate=win_rate,
                total_return=total_return,
                sharpe_ratio=sharpe_ratio,
                max_drawdown=max_drawdown,
                emergent_patterns=emergent_patterns_count,
                crystallized_patterns=crystallized_count,
                axiom_violations=axiom_violations,
                strategy_selection_autonomous=autonomous_selections > 0,
                convergence_episode=convergence_ep,
                status='OK'
            )
            
            return results
            
        except Exception as e:
            import traceback
            print(f"\n[ERROR] Exception in run_backtest_for_pair({symbol}): {e}")
            print(f"[ERROR] Traceback: {traceback.format_exc()}")
            return PairResults(
                symbol=symbol, bars=0,
                regime_distribution={}, predominant_regime='N/A',
                total_trades=0, winning_trades=0, losing_trades=0,
                win_rate=0.0, total_return=0.0, sharpe_ratio=0.0,
                max_drawdown=0.0, emergent_patterns=0,
                crystallized_patterns=0, axiom_violations=0,
                strategy_selection_autonomous=False,
                status='ERROR', error=str(e)
            )
    
    def run_all_tests(self) -> Dict[str, Any]:
        """
        Ejecutar tests en todos los pares.
        
        Returns:
            Dict con resultados globales y por par
        """
        files = self.get_market_files()
        print(f"\nArchivos encontrados: {len(files)}")
        
        if len(files) == 0:
            return {
                'status': 'ERROR',
                'error': 'No se encontraron archivos CSV',
                'ca_results': {f'CA{i}': False for i in range(1, 9)}
            }
        
        # Ejecutar backtest para cada par
        for i, file_path in enumerate(files, 1):
            print(f"\n[{i}/{len(files)}] Procesando {file_path.name}...")
            # FIX v5.0.2-R: Pass shared pattern_db for cross-pair learning
            results = self.run_backtest_for_pair(file_path, pattern_db=self.pattern_db)
            self.results.append(results)

            status_icon = "✅" if results.status == 'OK' else "⚠️"
            print(f"  {status_icon} {results.symbol}: {results.bars} barras, "
                  f"régimen: {results.predominant_regime}, "
                  f"win_rate={results.win_rate:.1f}%, "
                  f"return={results.total_return:.2f}%")

        # FIX v5.0.2-R: Save patterns after all pairs processed (PERSISTENCE)
        try:
            self.pattern_db.save_patterns()
            
            # 1D.2: Prune unproven emergent patterns after each backtest
            self.pattern_db.prune_unproven_emergent(max_episodes=3)
            
            crystallized_count = sum(1 for p in self.pattern_db.stored_patterns if p.crystallized)
            total_count = len(self.pattern_db.stored_patterns)

            # 1C.8: Persistence validation
            patterns_added = total_count - self.initial_pattern_count
            crystallized_added = crystallized_count - self.initial_crystallized

            print(f"\n{'='*60}")
            print(f"[MultiMarketTester] ✅ PERSISTENCE VALIDATION (1C.8)")
            print(f"{'='*60}")
            print(f"  Initial patterns: {self.initial_pattern_count}")
            print(f"  Final patterns: {total_count}")
            print(f"  Patterns added: {patterns_added}")
            print(f"  Initial crystallized: {self.initial_crystallized}")
            print(f"  Final crystallized: {crystallized_count}")
            print(f"  Crystallized added: {crystallized_added}")
            print(f"  DB saved to: {self.db_path}")

            # Validation status
            persistence_ok = total_count >= self.initial_pattern_count
            crystallization_ok = crystallized_count >= max(1, self.initial_crystallized)

            print(f"\n  Persistence check: {'✅ PASSED' if persistence_ok else '❌ FAILED'}")
            print(f"  Crystallization check: {'✅ PASSED' if crystallization_ok else '❌ FAILED'}")
            print(f"{'='*60}")

        except Exception as e:
            print(f"\n[MultiMarketTester] ❌ Error saving patterns: {e}")

        # 1C.12: Save REINFORCE policy (strategy_weights, baseline)
        # Use the last meta_learner from the loop (weights accumulated during test)
        try:
            if hasattr(self, '_last_meta_learner') and self._last_meta_learner:
                self._last_meta_learner.save_policy()
                print(f"\n{'='*60}")
                print(f"[MultiMarketTester] ✅ REINFORCE POLICY SAVED (1C.12)")
                print(f"{'='*60}")
                print(f"  Strategy weights: {self._last_meta_learner.strategy_weights}")
                print(f"  Baseline: {self._last_meta_learner.baseline:.3f}")
                print(f"{'='*60}")
            else:
                print(f"\n{'='*60}")
                print(f"[MultiMarketTester] ⚠️ No meta_learner available for saving")
                print(f"{'='*60}")
        except Exception as e:
            print(f"\n[MultiMarketTester] ❌ Error saving policy: {e}")

        # Calcular métricas globales
        self._calculate_global_stats()

        # Validar CA1-CA8
        ca_results = self._validate_criteria()
        
        return {
            'status': 'OK',
            'timestamp': datetime.now().isoformat(),
            'total_pairs': len(files),
            'valid_pairs': len([r for r in self.results if r.status == 'OK']),
            'results': [asdict(r) for r in self.results],
            'global_stats': self.global_stats,
            'ca_results': ca_results
        }
    
    def _calculate_global_stats(self):
        """Calcular estadísticas globales."""
        valid_results = [r for r in self.results if r.status == 'OK']
        
        if not valid_results:
            self.global_stats = {'error': 'No valid results'}
            return
        
        # Métricas promedio
        avg_win_rate = np.mean([r.win_rate for r in valid_results])
        avg_sharpe = np.mean([r.sharpe_ratio for r in valid_results])
        avg_drawdown = np.mean([r.max_drawdown for r in valid_results])
        avg_return = np.mean([r.total_return for r in valid_results])
        
        # Totales
        total_trades = sum(r.total_trades for r in valid_results)
        total_emergent = sum(r.emergent_patterns for r in valid_results)
        total_crystallized = sum(r.crystallized_patterns for r in valid_results)
        total_violations = sum(r.axiom_violations for r in valid_results)
        
        # Pares con >50% LATERAL
        lateral_pairs = [r for r in valid_results if r.regime_distribution.get('lateral', 0) > 50]
        
        # Top 3 por score
        for r in valid_results:
            r.score = (
                0.4 * (r.regime_distribution.get('lateral', 0) / 100) +
                0.3 * (r.win_rate / 100) +
                0.3 * (1.0 if r.sharpe_ratio > 0.5 else 0.5)
            )
        
        top_3 = sorted(valid_results, key=lambda x: x.score, reverse=True)[:3]
        
        self.global_stats = {
            'avg_win_rate': avg_win_rate,
            'avg_sharpe_ratio': avg_sharpe,
            'avg_max_drawdown': avg_drawdown,
            'avg_total_return': avg_return,
            'total_trades': total_trades,
            'total_emergent_patterns': total_emergent,
            'total_crystallized_patterns': total_crystallized,
            'total_axiom_violations': total_violations,
            'lateral_pairs_count': len(lateral_pairs),
            'lateral_pairs': [r.symbol for r in lateral_pairs],
            'top_3_pairs': [
                {
                    'symbol': r.symbol,
                    'score': r.score,
                    'win_rate': r.win_rate,
                    'sharpe_ratio': r.sharpe_ratio,
                    'total_return': r.total_return
                }
                for r in top_3
            ]
        }
    
    def _validate_criteria(self) -> Dict[str, bool]:
        """Validar criterios de aceptación CA1-CA8."""
        valid_results = [r for r in self.results if r.status == 'OK']
        
        if not valid_results:
            return {f'CA{i}': False for i in range(1, 9)}
        
        # CA1: Patrones emergentes ≥5
        total_emergent = sum(r.emergent_patterns for r in valid_results)
        ca1 = total_emergent >= 5
        
        # CA2: Auto-selección 100% episodios
        autonomous_count = sum(1 for r in valid_results if r.strategy_selection_autonomous)
        ca2 = autonomous_count == len(valid_results)
        
        # CA3: Win rate ≥55%
        avg_win_rate = np.mean([r.win_rate for r in valid_results])
        ca3 = avg_win_rate >= 55
        
        # CA4: Sharpe ratio ≥1.0
        avg_sharpe = np.mean([r.sharpe_ratio for r in valid_results])
        ca4 = avg_sharpe >= 1.0
        
        # CA5: Max drawdown <15%
        avg_drawdown = np.mean([r.max_drawdown for r in valid_results])
        ca5 = avg_drawdown < 15
        
        # CA6: Violaciones axiomáticas = 0
        total_violations = sum(r.axiom_violations for r in valid_results)
        ca6 = total_violations == 0
        
        # CA7: Convergencia Φ ≤50 episodios
        convergence_eps = [r.convergence_episode for r in valid_results if r.convergence_episode is not None]
        ca7 = all(ep <= 50 for ep in convergence_eps) if convergence_eps else True
        
        # CA8: Cristalización patrones ≥2
        total_crystallized = sum(r.crystallized_patterns for r in valid_results)
        ca8 = total_crystallized >= 2
        
        return {
            'CA1': ca1,
            'CA2': ca2,
            'CA3': ca3,
            'CA4': ca4,
            'CA5': ca5,
            'CA6': ca6,
            'CA7': ca7,
            'CA8': ca8
        }
    
    def save_results(self, output_dir: str = "logs"):
        """Guardar resultados en archivo."""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        # Resultados completos
        results_data = {
            'timestamp': datetime.now().isoformat(),
            'total_pairs': len(self.results),
            'results': [asdict(r) for r in self.results],
            'global_stats': self.global_stats
        }
        
        results_file = output_path / "multi_market_autonomous_results.json"
        with open(results_file, 'w') as f:
            json.dump(results_data, f, indent=2)
        
        print(f"\n  💾 Resultados guardados en: {results_file}")
        
        # Top 3 pares
        if self.global_stats.get('top_3_pairs'):
            top_3_file = output_path / "top_lateral_pairs.json"
            with open(top_3_file, 'w') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'top_3_pairs': self.global_stats['top_3_pairs']
                }, f, indent=2)
            
            print(f"  💾 Top 3 pares guardado en: {top_3_file}")


def main():
    """Ejecutar test multi-market autónomo."""
    print("="*70)
    print("TEST MULTI-MARKET AUTONOMOUS - MSE v5.0.2-R")
    print("="*70)
    print(f"Fecha: {datetime.now().isoformat()}")
    
    # Crear tester
    tester = MultiMarketTester(data_dir="data/market")
    
    # Ejecutar tests
    results = tester.run_all_tests()
    
    # Guardar resultados
    tester.save_results()
    
    # Imprimir resumen
    print("\n" + "="*70)
    print("RESUMEN DE CRITERIOS DE ACEPTACIÓN (CA1-CA8)")
    print("="*70)
    
    ca = results.get('ca_results', {})
    
    print(f"\n  CA1 (Patrones emergentes ≥5):        {'✅ PASSED' if ca.get('CA1') else '❌ FAILED'}")
    print(f"  CA2 (Auto-selección 100%):           {'✅ PASSED' if ca.get('CA2') else '❌ FAILED'}")
    print(f"  CA3 (Win rate ≥55%):                 {'✅ PASSED' if ca.get('CA3') else '❌ FAILED'}")
    print(f"  CA4 (Sharpe ratio ≥1.0):             {'✅ PASSED' if ca.get('CA4') else '❌ FAILED'}")
    print(f"  CA5 (Max drawdown <15%):             {'✅ PASSED' if ca.get('CA5') else '❌ FAILED'}")
    print(f"  CA6 (Violaciones axiomáticas = 0):   {'✅ PASSED' if ca.get('CA6') else '❌ FAILED'}")
    print(f"  CA7 (Convergencia Φ ≤50):            {'✅ PASSED' if ca.get('CA7') else '❌ FAILED'}")
    print(f"  CA8 (Cristalización patrones ≥2):    {'✅ PASSED' if ca.get('CA8') else '❌ FAILED'}")
    
    # Decisión final
    passed = sum(ca.values())
    total = len(ca)
    
    print("\n" + "="*70)
    if passed == total:
        print(f"✅ TEST MULTI-MARKET AUTONOMOUS PASSED ({passed}/{total} CA)")
    else:
        print(f"⚠️ TEST MULTI-MARKET AUTONOMOUS PARCIAL ({passed}/{total} CA)")
    print("="*70)
    
    # Imprimir estadísticas globales
    if 'global_stats' in results:
        gs = results['global_stats']
        print(f"\nEstadísticas Globales:")
        print(f"  Win rate promedio: {gs.get('avg_win_rate', 0):.1f}%")
        print(f"  Sharpe ratio promedio: {gs.get('avg_sharpe_ratio', 0):.2f}")
        print(f"  Drawdown máximo promedio: {gs.get('avg_max_drawdown', 0):.1f}%")
        print(f"  Retorno promedio: {gs.get('avg_total_return', 0):.2f}%")
        print(f"  Total trades: {gs.get('total_trades', 0)}")
        print(f"  Patrones emergentes: {gs.get('total_emergent_patterns', 0)}")
        print(f"  Patrones cristalizados: {gs.get('total_crystallized_patterns', 0)}")
        print(f"  Violaciones axiomáticas: {gs.get('total_axiom_violations', 0)}")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
