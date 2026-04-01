#!/usr/bin/env python3
"""
Test de Validación Fase 1D.2 - Ajustes de Trading MSE v5.0.2-R
============================================================

Valida que todos los ajustes 1D.2 están aplicados.

Criterios de Aceptación 1D.2:
- e_pt_trigger = 0.40 (Historical best from 1B.14-1B.16)
- S09: range_tolerance = 0.025
- S10/1B.12: min_support = 0.01, signature_precision = 1, debug_mode = False
- S11: volatility_window = 50
- S12: arbitrage_sigma_threshold = 5.0, min_gap_threshold = 0.15
- S13: max_holding_bars = 50
- R01-R03: regime_validator thresholds
"""

import sys
from pathlib import Path

# Configurar paths
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def test_phase1_adjustments():
    """Validar que todos los ajustes Fase 1 están aplicados"""
    
    print("="*70)
    print("TEST: Validación Ajustes Fase 1 - MSE v5.0.2-R")
    print("="*70)
    
    all_passed = True
    
    # =========================================================================
    # S09: range_tolerance
    # =========================================================================
    print("\nS09: range_tolerance (0.01 → 0.025)")
    try:
        from src.python.market.trading_bot import TradingBotAutonomous
        from src.python.market.market_pattern_database import MarketPatternDatabase
        
        pattern_db = MarketPatternDatabase()
        bot = TradingBotAutonomous('TEST/BTC', pattern_db=pattern_db)
        
        assert bot.range_tolerance == 0.025, f"S09 fallido: {bot.range_tolerance}"
        print(f"  ✅ range_tolerance = {bot.range_tolerance}")
    except Exception as e:
        print(f"  ❌ S09 fallido: {e}")
        all_passed = False
    
    # =========================================================================
    # S10/1B.12: min_support (0.05 → 0.01) + signature_precision + debug_mode
    # =========================================================================
    print("\nS10/1B.12: min_support (0.05 → 0.01) + signature_precision + debug_mode")
    try:
        from src.python.market.structural_induction import MarketStructuralInduction

        inductor = MarketStructuralInduction()

        assert inductor.min_support == 0.01, f"1B.12 min_support fallido: {inductor.min_support}"
        assert inductor.signature_precision == 1, f"1B.12 signature_precision fallido: {inductor.signature_precision}"
        assert inductor.debug_mode == False, f"1C.2 debug_mode fallido: {inductor.debug_mode}"
        print(f"  ✅ min_support = {inductor.min_support} (1B.12: 0.03→0.01)")
        print(f"  ✅ signature_precision = {inductor.signature_precision} (1B.12: 2→1)")
        print(f"  ✅ debug_mode = {inductor.debug_mode} (1C.2: False por defecto)")
    except Exception as e:
        print(f"  ❌ S10/1B.12 fallido: {e}")
        all_passed = False
    
    # =========================================================================
    # S11: volatility_window
    # =========================================================================
    print("\nS11: volatility_window (20 → 50)")
    try:
        from src.python.market.axiom_validator import AxiomValidator
        
        validator = AxiomValidator()
        
        assert validator.volatility_window == 50, f"S11 fallido: {validator.volatility_window}"
        print(f"  ✅ volatility_window = {validator.volatility_window}")
    except Exception as e:
        print(f"  ❌ S11 fallido: {e}")
        all_passed = False
    
    # =========================================================================
    # S12: arbitrage_sigma_threshold + min_gap_threshold
    # =========================================================================
    print("\nS12: arbitrage_sigma_threshold (3.0 → 5.0) + min_gap_threshold")
    try:
        from src.python.market.axiom_validator import AxiomValidator
        
        validator = AxiomValidator()
        
        assert validator.arbitrage_sigma_threshold == 5.0, f"S12 sigma fallido: {validator.arbitrage_sigma_threshold}"
        assert validator.min_gap_threshold == 0.15, f"S12 gap floor fallido: {validator.min_gap_threshold}"
        print(f"  ✅ arbitrage_sigma_threshold = {validator.arbitrage_sigma_threshold}")
        print(f"  ✅ min_gap_threshold = {validator.min_gap_threshold}")
    except Exception as e:
        print(f"  ❌ S12 fallido: {e}")
        all_passed = False
    
    # =========================================================================
    # S13: max_holding_bars
    # =========================================================================
    print("\nS13: max_holding_bars (NUEVO = 50)")
    try:
        from src.python.market.trading_bot import TradingBotAutonomous
        from src.python.market.market_pattern_database import MarketPatternDatabase
        
        pattern_db = MarketPatternDatabase()
        bot = TradingBotAutonomous('TEST/BTC', pattern_db=pattern_db)
        
        assert bot.max_holding_bars == 50, f"S13 fallido: {bot.max_holding_bars}"
        print(f"  ✅ max_holding_bars = {bot.max_holding_bars}")
        
        # Verificar que existe check_exit_conditions
        assert hasattr(bot, 'check_exit_conditions'), "S13: Falta método check_exit_conditions"
        print(f"  ✅ check_exit_conditions() método presente")
    except Exception as e:
        print(f"  ❌ S13 fallido: {e}")
        all_passed = False
    
    # =========================================================================
    # L04/1D.2: e_pt_trigger (0.55 → 0.50 → 0.40 for historical best)
    # =========================================================================
    print("\nL04/1D.2: e_pt_trigger (0.55 → 0.50 → 0.40)")
    try:
        from src.python.market.trading_bot import TradingBotAutonomous
        from src.python.market.market_pattern_database import MarketPatternDatabase

        pattern_db = MarketPatternDatabase()
        bot = TradingBotAutonomous('TEST/BTC', pattern_db=pattern_db)

        assert bot.e_pt_trigger == 0.40, f"1D.2 L04 fallido: {bot.e_pt_trigger}"
        print(f"  ✅ e_pt_trigger = {bot.e_pt_trigger} (1D.2: 0.50→0.40 historical best)")

        # Verificar que existe should_operate_pattern
        assert hasattr(bot, 'should_operate_pattern'), "L04: Falta método should_operate_pattern"
        print(f"  ✅ should_operate_pattern() método presente")
    except Exception as e:
        print(f"  ❌ L04/1D.2 fallido: {e}")
        all_passed = False
    
    # =========================================================================
    # R01-R03: regime_validator (1B.6: thresholds más permisivos para crypto)
    # =========================================================================
    print("\nR01-R03: regime_validator thresholds (1B.6: 0.05→0.08)")
    try:
        from src.python.market.regime_validator import RegimeValidator

        validator = RegimeValidator()

        # 1B.6: z_score_threshold 0.05 → 0.08 (60% más permisivo)
        assert validator.z_score_threshold == 0.08, f"R01 fallido: {validator.z_score_threshold}"
        # 1B.6: volatility_threshold 0.05 → 0.08 (60% más permisivo)
        assert validator.volatility_threshold == 0.08, f"R02 fallido: {validator.volatility_threshold}"
        # R03: trend_window
        assert validator.trend_window == 50, f"R03 fallido: {validator.trend_window}"
        # 1B.6: NUEVO trend_strength_threshold (ajustado de 0.02 → 0.005 para crypto)
        assert validator.trend_strength_threshold == 0.005, f"1B.6 trend_strength fallido: {validator.trend_strength_threshold}"

        print(f"  ✅ z_score_threshold = {validator.z_score_threshold} (1B.6: 0.05→0.08)")
        print(f"  ✅ volatility_threshold = {validator.volatility_threshold} (1B.6: 0.05→0.08)")
        print(f"  ✅ trend_window = {validator.trend_window}")
        print(f"  ✅ trend_strength_threshold = {validator.trend_strength_threshold} (1B.6: 0.005)")
    except Exception as e:
        print(f"  ❌ R01-R03 fallido: {e}")
        all_passed = False
    
    # =========================================================================
    # 1D.3: Crystallization threshold (0.95 → 0.70)
    # =========================================================================
    print("\n1D.3: Crystallization threshold (0.95 → 0.70)")
    try:
        from src.python.market.market_pattern_database import MarketStoredPattern
        from src.python.market.axioms import MarketRegime

        # Test 1: Pattern at exactly 0.70 should crystallize
        pattern = MarketStoredPattern(
            pattern_type='test_1d3',
            regime=MarketRegime.LATERAL,
            trigger_conditions={},
            entry_signal='buy',
            stop_loss_pct=0.025,
            take_profit_pct=0.03,
            confidence=0.70  # Exactly at threshold
        )
        
        crystallized = pattern.check_crystallization(threshold=0.70)
        assert crystallized == True, f"1D.3 fallido: pattern at 0.70 should crystallize"
        assert pattern.crystallized == True, "1D.3 fallido: crystallized flag should be True"
        
        print(f"  ✅ Crystallization at exactly 0.70: {crystallized}")
        print(f"  ✅ Pattern crystallized flag: {pattern.crystallized}")
    except Exception as e:
        print(f"  ❌ 1D.3 crystallization fallido: {e}")
        all_passed = False
    
    # =========================================================================
    # 1D.3: Meta-parameters (delta_plus 0.15→0.20, temperature 1.0→0.92)
    # =========================================================================
    print("\n1D.3: Meta-parameters validation")
    try:
        from src.python.learning.variational_meta_learner import MetaParameters

        params = MetaParameters()
        
        # 1D.3: delta_plus 0.15 → 0.20
        assert params.delta_plus == 0.20, f"1D.3 delta_plus fallido: {params.delta_plus}"
        
        # 1D.3: temperature 1.0 → 0.92
        assert params.temperature == 0.92, f"1D.3 temperature fallido: {params.temperature}"
        
        print(f"  ✅ delta_plus = {params.delta_plus} (1D.3: 0.15→0.20)")
        print(f"  ✅ temperature = {params.temperature} (1D.3: 1.0→0.92)")
    except Exception as e:
        print(f"  ❌ 1D.3 meta-parameters fallido: {e}")
        all_passed = False
    
    # =========================================================================
    # 1D.3: Position sizing premium tier (4.5% → 3.0% max)
    # =========================================================================
    print("\n1D.3: Position sizing premium tier (max 3.0%)")
    try:
        from src.python.market.trading_bot import TradingBotAutonomous

        bot = TradingBotAutonomous(symbol='TEST', initial_capital=10000)
        
        # Test with confidence >= 0.80 (premium tier)
        position = bot._calculate_position_size(
            price=100,
            stop_loss_pct=0.02,
            pattern_confidence=0.85,  # Premium tier
            regime='LATERAL'
        )
        
        # Calculate position percentage
        position_pct = (position * 100) / 10000  # Convert to percentage
        
        # 1D.3: Premium tier should be max 3.0% (was 4.5% in 1D.2)
        assert position_pct <= 3.0, f"1D.3 position sizing fallido: {position_pct}%"
        
        print(f"  ✅ Premium tier position: {position_pct:.2f}% (max 3.0%)")
    except Exception as e:
        print(f"  ❌ 1D.3 position sizing fallido: {e}")
        all_passed = False
    
    # =========================================================================
    # Resumen final
    # =========================================================================
    print("\n" + "="*70)
    if all_passed:
        print("✅ TODOS LOS AJUSTES FASE 1 + 1D.3 VALIDADOS")
        print("="*70)
        return True
    else:
        print("❌ ALGUNOS AJUSTES FASE 1 + 1D.3 FALLARON")
        print("="*70)
        return False


if __name__ == "__main__":
    success = test_phase1_adjustments()
    sys.exit(0 if success else 1)
