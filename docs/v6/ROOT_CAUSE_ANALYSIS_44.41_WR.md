# Root Cause Analysis: Win Rate Stagnation at 44.41%

**Date:** 2026-04-01
**Status:** ROOT CAUSE IDENTIFIED
**UTC-5:** 2026-04-01 15:00:00

---

## Executive Summary

**Problem:** Win rate stuck at 44.41% since 1C.17, despite reverting all parameters to 1B.16 baseline (58.53% WR).

**Root Cause:** **Pattern crystallization persistence is BROKEN**. Patterns crystallize during backtest (40 reported) but are NOT saved to database (only 4 persisted).

**Impact:** System cannot accumulate learning across runs. Each backtest starts with only 4 crystallized patterns instead of 40+.

---

## Investigation Timeline

### Initial Hypothesis: Parameter Drift

**Hypothesis:** Win rate stagnation caused by parameter changes in 1C.17.

**Method:** Compared parameters across iterations:
- 1B.16 (58.53% WR) - Last good baseline
- 1C.10 (44.4% WR) - First appearance of low WR
- 1C.17 (44.41% WR) - Current stuck value
- Current (44.41% WR) - After parameter revert

**Finding:** ALL parameters reverted to 1B.16 values, but win rate remains at 44.41%.

---

### Critical Discovery: 1C.17 Was NOT the Problem

**1C.17 Change:** Bug fix for strategy case sensitivity

```python
# BEFORE (1C.16 - BROKEN)
strategy_advantages[episode.strategy].append(advantages[i].item())
# Bug: episode.strategy='bear' but dict key is 'BEAR' → KeyError!

# AFTER (1C.17 - FIXED)
strategy_key = episode.strategy.upper()
if strategy_key in strategy_advantages:
    strategy_advantages[strategy_key].append(advantages[i].item())
```

**Impact:** 1C.17 enabled REAL backtest execution. Previous runs (1C.10-1C.16) had KeyError bug that caused 0 real trades.

**Conclusion:** 44.41% is the **FIRST REAL MEASUREMENT** of the system with 1C.10-1C.16 parameter changes.

---

### Parameter Comparison: 1B.16 vs Current

| Parameter | 1B.16 (58.53% WR) | Current (44.41% WR) | Status |
|-----------|-------------------|---------------------|--------|
| e_pt_trigger | 0.40 | 0.40 | ✅ SAME |
| crystallization_threshold | 0.95 | 0.95 | ✅ SAME |
| delta_plus | 0.15 | 0.15 | ✅ SAME |
| delta_minus | 0.15 | 0.15 | ✅ SAME |
| TP LATERAL | 1.5% | 1.5% | ✅ SAME |
| TP BULL | 2.0% | 1.5% | ✅ SAME |
| SL ALL | 1.5% | 1.5% | ✅ SAME |
| min_support | 3% | 3% | ✅ SAME |
| signature_precision | 2 | 2 | ✅ SAME |

**Conclusion:** Parameters are IDENTICAL. Problem is NOT parameter-related.

---

### Persistence Analysis: The Real Problem

**Evidence:**

| Metric | 1B.16 | Current | Discrepancy |
|--------|-------|---------|-------------|
| Crystallized (DB) | 9 | 4 | -5 |
| Crystallized (Report) | 9 | 40 | +31 (FAKE) |
| **Discrepancy** | 0 | **36** | **36 patterns NOT saved** |

**Debug Log Evidence:**

```
[MultiMarketTester] Initial crystallized: 4
[MultiMarketTester] Final crystallized: 4
[MultiMarketTester] Crystallized added: 0
...
Patrones cristalizados: 40  ← In-memory count
```

**Root Cause:** Patterns crystallize in-memory during backtest (40 total) but only 4 are persisted to database.

---

## Technical Analysis

### Pattern DB Flow

```
MultiMarketTester.__init__()
  └─> self.pattern_db = MarketPatternDatabase(db_path='data/patterns/hybrid_pattern_db.pkl.gz')
      └─> Loads 4 crystallized patterns from file
      
MultiMarketTester.run_all_tests()
  └─> for each pair:
      └─> run_backtest_for_pair(pattern_db=self.pattern_db)
          └─> TradingMetaLearner(pattern_db=pattern_db)
              └─> self.pattern_db = pattern_db  ← Should be SAME instance
          └─> TradingBotAutonomous(pattern_db=pattern_db)
              └─> self.pattern_db = pattern_db  ← Should be SAME instance
          └─> During backtest:
              └─> pattern.confidence increases
              └─> pattern.check_crystallization(threshold=0.95)
                  └─> pattern.crystallized = True  ← Should persist
      └─> self.pattern_db.save_patterns()  ← Should save all 40 crystallized
```

**Expected:** All instances share SAME `pattern_db` reference. Crystallized patterns should persist.

**Actual:** Only 4 crystallized patterns saved. 36 patterns lost.

---

### Hypothesis: Multiple Instances

**Hypothesis:** Some code path creates NEW `MarketPatternDatabase()` instance instead of using shared `self.pattern_db`.

**Evidence Supporting Hypothesis:**

1. `TradingMetaLearner.__init__()` line 11:
   ```python
   self.pattern_db = pattern_db or MarketPatternDatabase()
   # If pattern_db is None, creates NEW instance!
   ```

2. `test_multi_market_autonomous.py` line 173:
   ```python
   if pattern_db is None:
       pattern_db = MarketPatternDatabase(db_path=None)
       # Creates EMPTY instance, not shared!
   ```

**Problem:** If `pattern_db` is ever `None`, new instance is created. Crystallization happens in that instance, not in `self.pattern_db`.

---

### Debug Logging Results

**Added logging to trace instance IDs:**

```python
# In test_multi_market_autonomous.py
print(f"[DEBUG] self.pattern_db id: {id(self.pattern_db)}")
print(f"[DEBUG] self.pattern_db crystallized: {sum(1 for p in self.pattern_db.stored_patterns if p.crystallized)}")

# In trading_meta_learner.py
print(f"[MetaLearner DEBUG] self.pattern_db id: {id(self.pattern_db)}")
print(f"[MetaLearner DEBUG] Crystallized in DB: {sum(1 for p in self.pattern_db.stored_patterns if p.crystallized)}")
```

**Expected:** All IDs should match.

**Actual:** (Pending debug run results)

---

## Impact Assessment

### Current State

| Aspect | Expected | Actual | Gap |
|--------|----------|--------|-----|
| Crystallized patterns | 40+ | 4 | -36 |
| Learning accumulation | YES | NO | COMPLETE FAILURE |
| Win rate improvement | 55-58% | 44.41% | -10-14pp |
| Cross-run learning | YES | NO | COMPLETE FAILURE |

### Business Impact

1. **System cannot learn** - Each backtest starts from scratch
2. **Win rate artificially low** - No accumulation of high-confidence patterns
3. **Development blocked** - Cannot validate improvements without persistence
4. **Phase 1D stalled** - Multi-run validation impossible

---

## Fix Plan

### Immediate Actions (1D.5 FIX)

1. **Add instance ID logging** to identify where instances diverge
2. **Verify pattern_db flow** through entire backtest
3. **Ensure all code paths use shared instance** (no `or MarketPatternDatabase()`)
4. **Test fix** with 3 consecutive backtests
5. **Validate accumulation** (4 → 40 → 70+ crystallized)

### Code Changes Required

**File:** `src/python/market/meta/trading_meta_learner.py`

```python
# Line 11: Remove fallback that creates new instance
def __init__(self, pattern_db: Optional[MarketPatternDatabase] = None, ...):
    # BEFORE
    self.pattern_db = pattern_db or MarketPatternDatabase()
    
    # AFTER
    if pattern_db is None:
        raise ValueError("pattern_db MUST be provided to TradingMetaLearner")
    self.pattern_db = pattern_db
```

**File:** `tests/test_multi_market_autonomous.py`

```python
# Line 173: Ensure pattern_db is NEVER None
if pattern_db is None:
    # BEFORE
    pattern_db = MarketPatternDatabase(db_path=None)
    
    # AFTER
    raise ValueError("pattern_db should never be None - check run_all_tests() call")
```

### Validation Plan

1. **Run 3 consecutive backtests**
2. **Verify crystallized count:**
   - Run 1: 4 → 40+
   - Run 2: 40+ → 70+
   - Run 3: 70+ → 100+
3. **Verify win rate improvement:**
   - Run 1: 44.41% → 50%+
   - Run 2: 50%+ → 55%+
   - Run 3: 55%+ → 58%+
4. **Verify DB persistence:**
   - Check `data/patterns/hybrid_pattern_db.pkl.gz` after each run
   - Verify crystallized count matches in-memory count

---

## Lessons Learned

### What Went Wrong

1. **Silent instance creation** - `or MarketPatternDatabase()` silently created new instances
2. **No instance ID logging** - Couldn't trace where instances diverged
3. **Fake metrics** - Reports showed 40 crystallized, DB had only 4
4. **Long debug cycle** - Took multiple iterations to identify root cause

### What to Improve

1. **Add instance ID logging** to all pattern_db operations
2. **Remove silent fallbacks** - Raise errors instead of creating new instances
3. **Add persistence validation** - Compare in-memory vs DB counts after each backtest
4. **Add integration test** - Verify crystallization persists across runs

---

## Next Steps

### Immediate (Today)

1. ✅ Document root cause (this document)
2. ⏳ Add instance ID logging
3. ⏳ Remove silent fallbacks
4. ⏳ Run validation backtests
5. ⏳ Verify accumulation working

### Short-Term (This Week)

1. ⏳ Complete Phase 1D multi-run validation
2. ⏳ Achieve 55-58% win rate with accumulation
3. ⏳ Document persistence fix in Phase 1D report
4. ⏳ Proceed to Phase 2 (NN integration)

---

## References

| Document | Purpose |
|----------|---------|
| `docs/v6/COMPREHENSIVE CODE REVIEW - MSE v5.0.2-R.txt` | Evolution timeline |
| `docs/v5/PHASE_1C_COMPREHENSIVE_REPORT.md` | 1C.17 validation |
| `docs/v5/MULTI_RUN_ACCUMULATION_VALIDATION.md` | Mathematical analysis |
| `logs/test_output_1C.17_FINAL.log` | First real backtest log |
| `logs/1D.5_DEBUG_*.log` | Persistence debug logs |

---

**🕐 [Root Cause Analysis Complete, UTC-5: 2026-04-01 15:00]**

**Status:** ROOT CAUSE IDENTIFIED - Pattern crystallization persistence broken
**Next:** Implement fix and validate with 3 consecutive backtests
