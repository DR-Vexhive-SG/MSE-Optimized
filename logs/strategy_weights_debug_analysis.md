# Strategy Weights Debug Analysis Report
**Date:** 2026-03-31  
**Iteration:** Run 2 (Post-Fix)  
**Test:** `tests/test_multi_market_autonomous.py --dataset ETP/USD --max-bars 200`

---

## 1. Executive Summary

### ✅ FIXED: Episode Recording with Actual PnL
- **Before Fix:** All episodes recorded with `pnl=0.00` (trade not closed yet)
- **After Fix:** Episodes now recorded with **ACTUAL PnL** values:
  - `ACTUAL PnL=3.7417` (time_exit)
  - `ACTUAL PnL=-15.5896` (time_exit)
  - `ACTUAL PnL=388.6608` (take_profit)
  - `ACTUAL PnL=67.3224` (time_exit)

### ⚠️ REMAINING ISSUE: Zero Gradients from log_prob=0
- Many `log_prob=0.0000` values observed (when strategy probability = 1.0)
- This causes `loss = -(log_probs * advantages).mean()` to be ~0
- Result: REINFORCE gradients are near-zero, no meaningful weight updates

### ⚠️ SECONDARY ISSUE: Weight Clamping
- Strategy weights grow due to `*= 1.01` in `select_strategy()`
- Clamp `max(0.1, min(10.0, ...))` resets weights to 10.0
- This masks any small gradient updates

---

## 2. Root Cause Analysis

### Primary Root Cause: log_prob = 0.0000

**Observation:**
```
[MetaLearner DEBUG] select_strategy: selected=LATERAL, log_prob=0.0000
[MetaLearner DEBUG] select_strategy: selected=BULL, log_prob=0.0000
```

**Why this happens:**
```python
# In select_strategy():
log_prob = torch.log(probs[strategy_idx])
```

When `probs[strategy_idx] = 1.0` (or very close), `log(1.0) = 0.0`.

**Why probability = 1.0:**
1. **Low temperature:** `tau = self.meta_params.temperature` (default 1.0, but may decrease)
2. **Skewed scores:** One strategy dominates due to:
   - Pattern confidence sums heavily favoring one regime
   - `strategy_weights` amplifying the difference via `*= 1.01`

**Impact on REINFORCE:**
```python
loss = -(log_probs * advantages.detach()).mean()
# When log_probs = 0:
loss = -(0 * advantages).mean() = 0

gradients[f'weight_{strategy}'] = loss.item() * avg_advantage * learning_rate
# When loss = 0:
gradients = 0 * avg_advantage * 0.01 = 0
```

### Secondary Root Cause: Premature Episode Recording (FIXED)

**Before Fix:**
```python
# In process_state() - called at trade ENTRY:
pnl = trade.pnl if trade.is_closed else 0.0  # Always 0.0!
self.meta_learner.record_episode(..., pnl=pnl)
```

**After Fix:**
```python
# In _close_position() - called at trade EXIT:
actual_pnl = last_trade.pnl  # Real PnL value!
self.meta_learner.record_episode(..., pnl=actual_pnl)
```

---

## 3. Evidence from Debug Logs

### Episode Recording Now Working:
```
[MetaLearner DEBUG] _close_position: Recording episode with ACTUAL PnL=3.7417, reason=time_exit
[MetaLearner DEBUG] record_episode: strategy=bear, pnl=3.74, log_probs_history len=1, rewards_history len=1

[MetaLearner DEBUG] _close_position: Recording episode with ACTUAL PnL=-15.5896, reason=time_exit
[MetaLearner DEBUG] record_episode: strategy=bear, pnl=-15.59, log_probs_history len=1, rewards_history len=1

[MetaLearner DEBUG] _close_position: Recording episode with ACTUAL PnL=388.6608, reason=take_profit
[MetaLearner DEBUG] record_episode: strategy=bull, pnl=388.66, log_probs_history len=1, rewards_history len=1
```

### Weight Updates Still Zero:
```
[MetaLearner DEBUG] update_strategy_policy called
[MetaLearner DEBUG] log_probs_history length: 1
[MetaLearner DEBUG] rewards_history length: 1
[MetaLearner DEBUG] returns: tensor([-15.5896]), numel: 1
[MetaLearner DEBUG] baseline: 7.9127
[MetaLearner DEBUG] advantages: tensor([-23.5023]), mean: -23.5023
[MetaLearner DEBUG] loss: -0.000000          ← ZERO despite non-zero advantages!
[MetaLearner DEBUG] gradients: {'weight_BULL': 0.0, ...}  ← ALL ZERO
```

### Weight Clamping in Action:
```
[MetaLearner DEBUG] BULL: 12.824320 + -0.000000 = 12.824320 (clamped: 10.000000)
[MetaLearner DEBUG] LATERAL: 22.612712 + -0.000000 = 22.612712 (clamped: 10.000000)
[MetaLearner DEBUG] strategy_weights AFTER: {'BULL': 10.0, 'LATERAL': 10.0, ...}
```

---

## 4. Proposed Fixes

### Fix 1: Add Minimum Exploration (Prevent log_prob=0)

**File:** `src/python/market/meta/trading_meta_learner.py`

**Change in `select_strategy()`:**
```python
# BEFORE:
log_prob = torch.log(probs[strategy_idx])

# AFTER: Add epsilon-floor to prevent log(0) and log(1)
epsilon = 1e-6
clipped_prob = torch.clamp(probs[strategy_idx], epsilon, 1.0 - epsilon)
log_prob = torch.log(clipped_prob)
```

### Fix 2: Remove Simple Reinforcement from select_strategy()

**Problem:** The `*= 1.01` update in `select_strategy()` causes unbounded growth:
```python
# CURRENT (problematic):
self.strategy_weights[selected_strategy] *= 1.01  # Called EVERY selection!
```

**Solution:** Remove this line - REINFORCE should be the ONLY weight update mechanism:
```python
# REMOVE this line from select_strategy():
# self.strategy_weights[selected_strategy] *= 1.01
```

### Fix 3: Increase Temperature for More Exploration

**File:** `src/python/learning/variational_meta_learner.py` or via MetaParameters

**Change:**
```python
# Increase minimum temperature
meta_params.temperature = max(0.5, meta_params.temperature)  # Was 0.1
```

### Fix 4: Adjust Gradient Calculation

**Current:**
```python
gradients[f'weight_{strategy}'] = loss.item() * avg_advantage * self.learning_rate
```

**Issue:** All strategies get same gradient. Should be strategy-specific.

**Proposed:**
```python
# Calculate per-strategy gradient based on selection frequency and advantage
for strategy in self.strategy_weights:
    # Find episodes where this strategy was selected
    strategy_advantages = []
    for i, episode in enumerate(self.episodes):
        if episode.strategy == strategy:
            strategy_advantages.append(advantages[i].item())
    
    if strategy_advantages:
        avg_strategy_advantage = np.mean(strategy_advantages)
        gradients[f'weight_{strategy}'] = avg_strategy_advantage * self.learning_rate
    else:
        gradients[f'weight_{strategy}'] = 0.0
```

---

## 5. Files Modified

| File | Change | Status |
|------|--------|--------|
| `src/python/market/meta/trading_meta_learner.py` | Added debug logging to `select_strategy()`, `update_strategy_policy()`, `record_episode()`, `update_pattern_effectiveness()` | ✅ Complete |
| `src/python/market/trading_bot.py` | Added `strategy`, `log_prob`, `regime`, `patterns_used` fields to `BotPosition` | ✅ Complete |
| `src/python/market/trading_bot.py` | Store `current_regime` and `current_patterns` in `select_strategy()` | ✅ Complete |
| `src/python/market/trading_bot.py` | Removed premature `record_episode()` from `process_state()` | ✅ Complete |
| `src/python/market/trading_bot.py` | Added proper `record_episode()` call to `_close_position()` with actual PnL | ✅ Complete |

---

## 6. Validation Results

### Before Fix (Run 1):
```
record_episode: pnl=0.00 (always)
returns: tensor([0., 0.])
advantages: tensor([0., 0.])
loss: -0.000000
gradients: all zero
strategy_weights: UNCHANGED
```

### After Fix (Run 2):
```
record_episode: pnl=3.74, -15.59, 388.66, 67.32, ... (ACTUAL values!)
returns: tensor([-15.5896]), tensor([388.6608]), ... (non-zero!)
advantages: tensor([-23.5023]), ... (non-zero!)
loss: -0.000000 (still zero due to log_prob=0)
gradients: all zero (still zero due to loss=0)
strategy_weights: Changing due to *=1.01, but clamped to 10.0
```

### Next Steps Required:
1. ✅ Fix episode recording (COMPLETE)
2. ⏳ Fix log_prob=0 issue (needs temperature/epsilon adjustment)
3. ⏳ Remove `*= 1.01` from select_strategy()
4. ⏳ Improve per-strategy gradient calculation

---

## 7. Recommendations

### Immediate Actions:
1. **Remove `*= 1.01` from `select_strategy()`** - This is causing weight instability
2. **Add epsilon-floor to probability clipping** - Prevents log(0) and log(1)
3. **Increase minimum temperature** - Encourages more exploration

### Medium-term Improvements:
1. **Implement per-strategy gradients** - Current approach gives same gradient to all strategies
2. **Add gradient clipping** - Prevents explosive weight updates
3. **Consider baseline decay adjustment** - Current `baseline_decay=0.99` may be too high

### Testing:
1. Run with `--max-bars 500` to get more episodes per update
2. Monitor `log_probs_history length` to ensure episodes are being collected
3. Check that `update_strategy_policy()` is called with ≥5 episodes for stable gradients

---

## 8. Conclusion

**Primary Issue FIXED:** Episodes are now recorded with actual PnL values instead of 0.

**Secondary Issue IDENTIFIED:** `log_prob=0.0000` causes zero gradients, preventing REINFORCE updates.

**Action Required:** Implement Fix 1 (epsilon-floor) and Fix 2 (remove `*= 1.01`) to enable meaningful strategy weight updates.
