# MSE v5.0.2-R - PATTERN CATALOG

**Version:** 3.0 - Pattern Enrichment Edition
**Date:** 2026-03-30
**Total Patterns:** 14 (6 base + 8 enrichment)
**UTC-5:** 2026-03-30 22:30:00

---

## 📊 Pattern Summary

| Category | Count | Patterns |
|----------|-------|----------|
| **Base Patterns (QC v1.0)** | 6 | breakout_resistance, pullback_support, breakdown_support, rally_resistance, range_buy_low, range_sell_high |
| **Reversal Patterns** | 4 | head_and_shoulders, inverse_head_shoulders, double_top, double_bottom |
| **Continuation Patterns** | 4 | ascending_triangle, descending_triangle, flag_pennant, cup_and_handle |
| **TOTAL** | **14** | |

---

## 📋 Pattern Details by Regime

### **BULL Regime (8 patterns)**

| # | Pattern | Type | Signal | TP | SL | TP/SL | Confidence | Complexity |
|---|---------|------|--------|----|----|-------|------------|------------|
| 1 | breakout_resistance | Base | buy | 5% | 2.5% | 2.0 | 0.60 | 2.0 |
| 2 | pullback_support | Base | buy | 5% | 2.5% | 2.0 | 0.55 | 2.5 |
| 7 | head_and_shoulders | Reversal | sell | 8% | 3% | 2.67 | 0.70 | 5.0 |
| 9 | double_top | Reversal | sell | 6% | 2.5% | 2.4 | 0.65 | 4.0 |
| 11 | ascending_triangle | Continuation | buy | 5% | 2% | 2.5 | 0.60 | 3.5 |
| 13 | flag_pennant | Continuation | buy | 5% | 2% | 2.5 | 0.62 | 3.0 |
| 14 | cup_and_handle | Continuation | buy | 10% | 3% | 3.33 | 0.75 | 6.0 |

### **BEAR Regime (7 patterns)**

| # | Pattern | Type | Signal | TP | SL | TP/SL | Confidence | Complexity |
|---|---------|------|--------|----|----|-------|------------|------------|
| 3 | breakdown_support | Base | sell | 5% | 2.5% | 2.0 | 0.60 | 2.0 |
| 4 | rally_resistance | Base | sell | 5% | 2.5% | 2.0 | 0.55 | 2.5 |
| 8 | inverse_head_shoulders | Reversal | buy | 8% | 3% | 2.67 | 0.70 | 5.0 |
| 10 | double_bottom | Reversal | buy | 6% | 2.5% | 2.4 | 0.65 | 4.0 |
| 12 | descending_triangle | Continuation | sell | 5% | 2% | 2.5 | 0.60 | 3.5 |
| 13b | flag_pennant_bear | Continuation | sell | 5% | 2% | 2.5 | 0.62 | 3.0 |

### **LATERAL Regime (2 patterns)**

| # | Pattern | Type | Signal | TP | SL | TP/SL | Confidence | Complexity |
|---|---------|------|--------|----|----|-------|------------|------------|
| 5 | range_buy_low | Base | buy | 3% | 2.5% | 1.2 | 0.65 | 3.0 |
| 6 | range_sell_high | Base | sell | 3% | 2.5% | 1.2 | 0.65 | 3.0 |

---

## 🔍 Pattern Descriptions

### **Base Patterns (QC v1.0)**

#### 1. breakout_resistance (BULL)
**Description:** Price breaks above resistance with volume confirmation
**Trigger:** `close_t > max(high_{t-20:t-1}) ∧ volume_t > 1.5·volume_mean`
**TP/SL:** 5% / 2.5% (2.0 ratio)
**Expected Win Rate:** 55-60%

#### 2. pullback_support (BULL)
**Description:** Price pulls back to support in uptrend
**Trigger:** `close_t ∈ [support·1.002, support·1.005] ∧ R(t)=BULL`
**TP/SL:** 5% / 2.5% (2.0 ratio)
**Expected Win Rate:** 50-55%

#### 3. breakdown_support (BEAR)
**Description:** Price breaks below support with volume confirmation
**Trigger:** `close_t < min(low_{t-20:t-1}) ∧ volume_t > 1.5·volume_mean`
**TP/SL:** 5% / 2.5% (2.0 ratio)
**Expected Win Rate:** 55-60%

#### 4. rally_resistance (BEAR)
**Description:** Price rallies to resistance in downtrend
**Trigger:** `close_t ∈ [resistance·0.995, resistance·0.998] ∧ R(t)=BEAR`
**TP/SL:** 5% / 2.5% (2.0 ratio)
**Expected Win Rate:** 50-55%

#### 5. range_buy_low (LATERAL)
**Description:** Price at range low in sideways market
**Trigger:** `close_t ∈ [range_low, range_low·1.01] ∧ R(t)=LATERAL`
**TP/SL:** 3% / 2.5% (1.2 ratio)
**Expected Win Rate:** 55-60%

#### 6. range_sell_high (LATERAL)
**Description:** Price at range high in sideways market
**Trigger:** `close_t ∈ [range_high·0.99, range_high] ∧ R(t)=LATERAL`
**TP/SL:** 3% / 2.5% (1.2 ratio)
**Expected Win Rate:** 55-60%

---

### **🆕 Reversal Patterns (Phase 1C.7-1C.14)**

#### 7. head_and_shoulders (BULL→BEAR)
**Description:** Classic reversal pattern with peak (head) between two lower peaks (shoulders)
**Trigger:**
- `reversal_pattern: head_and_shoulders`
- `volume_declining: True`
- `neckline_break: True`
- `confirmation_candles: 2`
**Signal:** SELL (short on reversal)
**TP/SL:** 8% / 3% (2.67 ratio)
**Confidence:** 0.70 (high)
**Complexity:** 5.0 (complex)
**Expected Win Rate:** 65-70%

#### 8. inverse_head_and_shoulders (BEAR→BULL)
**Description:** Inverse H&S with trough (head) between two higher troughs
**Trigger:**
- `reversal_pattern: inverse_head_and_shoulders`
- `volume_increasing: True`
- `neckline_break: True`
- `confirmation_candles: 2`
**Signal:** BUY (long on reversal)
**TP/SL:** 8% / 3% (2.67 ratio)
**Confidence:** 0.70 (high)
**Complexity:** 5.0 (complex)
**Expected Win Rate:** 65-70%

#### 9. double_top (BULL→BEAR)
**Description:** M pattern - two consecutive peaks at same resistance
**Trigger:**
- `reversal_pattern: double_top`
- `resistance_touches: 2`
- `volume_second_peak_lower: True`
- `confirmation_candles: 1`
**Signal:** SELL
**TP/SL:** 6% / 2.5% (2.4 ratio)
**Confidence:** 0.65
**Complexity:** 4.0
**Expected Win Rate:** 60-65%

#### 10. double_bottom (BEAR→BULL)
**Description:** W pattern - two consecutive troughs at same support
**Trigger:**
- `reversal_pattern: double_bottom`
- `support_touches: 2`
- `volume_second_trough_higher: True`
- `confirmation_candles: 1`
**Signal:** BUY
**TP/SL:** 6% / 2.5% (2.4 ratio)
**Confidence:** 0.65
**Complexity:** 4.0
**Expected Win Rate:** 60-65%

---

### **🆕 Continuation Patterns (Phase 1C.7-1C.14)**

#### 11. ascending_triangle (BULL)
**Description:** Higher lows + flat resistance, bullish breakout expected
**Trigger:**
- `continuation_pattern: ascending_triangle`
- `higher_lows_count: 3`
- `resistance_flat: True`
- `volume_increasing: True`
**Signal:** BUY
**TP/SL:** 5% / 2% (2.5 ratio)
**Confidence:** 0.60
**Complexity:** 3.5
**Expected Win Rate:** 58-63%

#### 12. descending_triangle (BEAR)
**Description:** Lower highs + flat support, bearish breakdown expected
**Trigger:**
- `continuation_pattern: descending_triangle`
- `lower_highs_count: 3`
- `support_flat: True`
- `volume_increasing: True`
**Signal:** SELL
**TP/SL:** 5% / 2% (2.5 ratio)
**Confidence:** 0.60
**Complexity:** 3.5
**Expected Win Rate:** 58-63%

#### 13. flag_pennant (BULL/BEAR)
**Description:** Sharp move (flagpole) + consolidation (flag/pennant)
**Trigger (BULL):**
- `continuation_pattern: flag_pennant`
- `flagpole_surge_pct_min: 0.05` (5% surge)
- `consolidation_bars: 5`
- `volume_declining_consolidation: True`
**Trigger (BEAR):**
- `flagpole_drop_pct_min: 0.05` (5% drop)
**Signal:** BUY (BULL) / SELL (BEAR)
**TP/SL:** 5% / 2% (2.5 ratio)
**Confidence:** 0.62
**Complexity:** 3.0
**Expected Win Rate:** 60-65%

#### 14. cup_and_handle (BULL)
**Description:** U-shaped bottom (cup) + small consolidation (handle)
**Trigger:**
- `continuation_pattern: cup_and_handle`
- `cup_depth_pct: 0.15` (15% depth)
- `handle_retracement_pct: 0.05` (5% handle)
- `cup_duration_bars_min: 50`
- `volume_u_shape: True`
**Signal:** BUY
**TP/SL:** 10% / 3% (3.33 ratio)
**Confidence:** 0.75 (HIGHEST)
**Complexity:** 6.0 (MOST COMPLEX)
**Expected Win Rate:** 70-75%

---

## 📈 Pattern Performance Expectations

### **By Category**

| Category | Count | Avg Confidence | Avg TP/SL | Expected Win Rate |
|----------|-------|----------------|-----------|-------------------|
| **Base** | 6 | 0.60 | 1.73 | 55-60% |
| **Reversal** | 4 | 0.675 | 2.47 | 60-70% |
| **Continuation** | 4 | 0.64 | 2.71 | 60-75% |
| **TOTAL** | **14** | **0.64** | **2.23** | **57-65%** |

### **By Regime**

| Regime | Patterns | Avg TP/SL | Expected Win Rate |
|--------|----------|-----------|-------------------|
| **BULL** | 8 | 2.38 | 58-65% |
| **BEAR** | 7 | 2.23 | 58-65% |
| **LATERAL** | 2 | 1.2 | 55-60% |

---

## 🎯 Expected Impact (Phase 1C.7-1C.14)

| Metric | 1C.6 Baseline | 1C.14 Target | Δ |
|--------|---------------|--------------|---|
| **Pattern Count** | 6 | 14 | +133% |
| **Win Rate** | 57.4% | 60-65% | +2.6 to +7.6pp |
| **Sharpe Ratio** | -55.84 | -40 to -30 | +15 to +25 |
| **Crystallized Patterns** | 7 | 10-12 | +3 to +5 |
| **CA Passing** | 6/8 | 7-8/8 | +1 to +2 |

---

## 📝 Implementation Notes

### **Pattern Detection Requirements**

1. **Reversal Patterns (7, 8, 9, 10):**
   - Require historical price data (50-100 bars minimum)
   - Volume confirmation critical
   - Higher complexity (4.0-5.0)
   - Wider TP/SL for reversal moves

2. **Continuation Patterns (11, 12, 13, 14):**
   - Require trend identification
   - Volume patterns during consolidation
   - Medium complexity (3.0-6.0)
   - cup_and_handle is most complex (6.0)

3. **Base Patterns (1-6):**
   - Already implemented and tested
   - Lower complexity (2.0-3.0)
   - Proven performance in 1C.6

### **Next Steps**

1. ✅ **Pattern Implementation:** COMPLETE (14 patterns defined)
2. ⏳ **Pattern Detection Logic:** Implement trigger conditions in `market_pattern_database.py::_check_trigger_conditions()`
3. ⏳ **Backtest Validation:** Run multi-market test with 14 patterns
4. ⏳ **Performance Analysis:** Compare vs 1C.6 baseline

---

**🕐 [Fase: 1C Pattern Enrichment, Paso: Catalog Complete, UTC-5: 2026-03-30 22:30]**
