# MACD-TD V6 Strategy Intake Report

## Strategy Summary

The MACD-TD V6 strategy is a multi-timeframe trading system combining MACD divergence signals for entry with TD9 (Tom DeMark) setup signals for exit management.

**Entry Timeframe**: 15m  
**Management Timeframes**: 1m, 3m, 5m, 30m

### Indicators Used

- MACD (12, 26, 9)
- Fast MACD (8, 17, 6)
- ATR (14)
- EMA (20), EMA (60)
- RSI (14)
- Volume ratio (20-period MA)
- TD9 setup signals
- Local extrema detection

## Translated Rules

### Entry Rules

**Long Entry**:
- Bullish MACD divergence on 15m (price makes lower low, MACD makes higher low)
- Divergence strength >= min_divergence_strength (default 0.25)
- Optional buy filter: at least 2 of 3 conditions met:
  - RSI < buy_rsi_threshold (default 40)
  - Close < EMA60
  - Volume ratio > buy_volume_ratio (default 0.8)

**Short Entry**:
- Bearish MACD divergence on 15m (price makes higher high, MACD makes lower high)
- Divergence strength >= min_divergence_strength

### Exit Rules

**Partial Exits**:
- 1m TD9 opposite signal: close 25%
- 3m TD9 opposite signal: close 20%
- 5m TD9 opposite signal: close 25%

**Full Close**:
- 15m TD9 opposite signal
- Optional: 30m TD9 opposite signal

**Initial Stop**:
- Long: divergence low - ATR * 1.5
- Short: divergence high + ATR * 1.5

### Add/Re-entry Rules

- 15m TD9 same-direction signal after entry: add 30% if in profit and outside protection period
- 3m or 5m same-direction TD9 can add back reduced size after partial exit

### Trailing Stop Rules

- Long: stop = max(highest - ATR * 2.0, highest * 0.95)
- Short: stop = min(lowest + ATR * 2.0, lowest * 1.05)
- Update only on completed bars

### Position Sizing

- Risk per trade: 5% of equity
- Strength multiplier applied to size
- Max position: 20% of equity

## Architecture Decomposition

### Feature Layer (Implemented in quant_stack)

| Feature | Status | Source |
|---------|--------|--------|
| MACD | Available | quant_stack.indicators.polars.momentum (via custom) |
| ATR | Available | quant_stack.indicators.polars.volatility.atr |
| EMA | Available | quant_stack.indicators.polars.trend.ema |
| RSI | Available | quant_stack.indicators.polars.momentum.rsi |
| Volume Ratio | Available | Custom expression |
| Local Extrema | Partially Available | Need confirmation delay handling |
| TD Setup | Missing | Must implement |
| Divergence Detection | Missing | Must implement |
| Multi-timeframe ASOF | Available | Polars.asof_join |

### Signal/Event Layer (To Implement)

- Long entry candidate signals
- Short entry candidate signals
- TD partial-exit events
- TD full-close events
- Add/re-entry events
- Trailing stop update events

### Path-dependent Simulation Layer (Research Phase)

- Position state management
- Partial exit tracking
- Add/re-entry logic
- Trailing stop updates
- Risk sizing calculations
- Cost tracking
- Trade logs

## Known Leakage Risks

### 1. Same-bar Execution Risk
**Status**: Flagged as risk in audit

Original script computes signal using 15m close at index i and enters at current close price. This may be lookahead if signal is only known after the bar closes.

**Safe Policy**: Signal/event detected on completed bar t executes no earlier than next executable bar (t+1 open).

### 2. Nearest Timestamp Leakage Risk
**Status**: Flagged as risk in audit

Original script uses absolute nearest timestamp matching:
```python
time_diff = abs(lower_tf_time - current_15m_time)
idx = idxmin()
```
This can select future lower-timeframe bars.

**Safe Policy**: Use asof backward semantics only - selected_time <= T

### 3. Local Extrema Confirmation Delay Risk
**Status**: Documented in audit

Original local extrema detection uses a window that requires bars after the candidate extrema. This means divergence is only known after confirmation delay.

**Safe Policy**: Divergence signal timestamp must be the confirmation timestamp, not the extrema timestamp.

### 4. Multi-timeframe Alignment Risk
**Status**: Documented in audit

Lower timeframe selection must use backward asof only with close_time <= current_15m_close_time.

### 5. Trailing Stop Intrabar Assumption Risk
**Status**: Documented in audit

Original code checks 15m high/low against stop but may use 5m close for management.

**Safe Policy**: Document stop execution assumption conservatively - stop fills if touched, worst case.

### 6. Partial Exit Price Assumption Risk
**Status**: Documented in audit

Original uses current 5m close for partial exits while iterating 15m bars.

**Safe Policy**: Align with completed 5m bars only.

### 7. Live API Dependency Risk
**Status**: Not present in intake

The intake pipeline uses synthetic data only.

### 8. pandas/TA-Lib Dependency Risk
**Status**: Present in original, must avoid in core

Original uses pandas and TA-Lib. Core implementation must use Polars/NumPy or existing indicator modules.

## Safe Execution Assumptions

- **Primary Event Clock**: 15m completed bars
- **Lower Timeframe Alignment**: asof_backward (select bar with close_time <= current_15m_close_time)
- **Extrema Confirmation Policy**: delayed_until_confirmed
- **Stop Fill Policy**: conservative_stop_price
- **Same Bar Event Ordering**: conservative_adverse_first
- **Entry Execution**: next_15m_open
- **Trailing Stop Update Policy**: completed_bars_only
- **Partial Exit Execution**: next_lower_tf_bar_open
- **Full Close Execution**: next_15m_bar_open_after_confirmed

## Implementation Gaps

### Must Implement Before Phase 19B

1. TD9 setup detection function (compute_td_setup)
2. MACD divergence detection with confirmation delay
3. Multi-timeframe asof join with backward semantics
4. Path-dependent state machine for partial exits
5. Trailing stop with monotonicity guarantees

### Should Implement Later

1. Real-time TD setup countdown
2. Dynamic divergence strength calculation
3. Multi-symbol backtest capability

## What Was Tested in Phase 19A

- Schema validation for all Pydantic models
- Query YAML parsing
- Strategy idea artifact generation
- Experiment plan artifact generation
- Leakage audit artifact generation
- Execution semantics artifact generation
- Feature availability report generation
- Same-bar execution risk flagging
- Nearest timestamp leakage risk flagging
- Local extrema confirmation delay documentation
- TD setup detection (deterministic)
- Trailing stop monotonicity (long moves up, short moves down)
- No live Binance calls made
- No broker/account/order imports used
- No pandas import in core schemas

## What Was NOT Tested in Phase 19A

- Economic profitability
- Parameter optimization
- Real backtest execution
- Live trading integration
- Performance benchmarks

## Eligibility Decision

**Verdict**: `eligible_with_risks`

The strategy is eligible for Phase 19B with identified risks that must be addressed:

1. **Fix same-bar execution**: Implement next-bar-open execution policy
2. **Fix nearest timestamp matching**: Replace with asof backward semantics
3. **Implement divergence confirmation delay**: Track extrema timestamp separately from signal timestamp
4. **Avoid pandas/TA-Lib in core**: Use Polars and existing indicators

## Recommended Next Phase

**Phase 19B — Faithful Deterministic MACD-TD V6 Backtest Prototype**

Before proceeding:
1. Fix same-bar execution in signal detection
2. Implement asof backward for multi-timeframe alignment
3. Add divergence confirmation delay tracking
4. Re-run Phase 19A to verify fixes

If eligibility changes to `eligible` after fixes, proceed to Phase 19B for deterministic backtest prototype.

## Files Created

- `quant_stack/research/strategy_intake/__init__.py`
- `quant_stack/research/strategy_intake/macd_td_v6_schemas.py`
- `quant_stack/research/strategy_intake/macd_td_v6_intake.py`
- `quant_stack/research/strategy_intake/macd_td_v6_audit.py`
- `examples/pipeline_queries/macd_td_v6_intake.yaml`
- `scripts/run_macd_td_v6_intake.py`
- `tests/research/test_macd_td_v6_intake.py`
- `tests/research/test_macd_td_v6_leakage_audit.py`
- `docs/research/MACD_TD_V6_INTAKE.md`

## Commands to Run

```bash
# Run intake pipeline
python scripts/run_macd_td_v6_intake.py examples/pipeline_queries/macd_td_v6_intake.yaml

# Run tests
pytest tests/research/test_macd_td_v6_intake.py tests/research/test_macd_td_v6_leakage_audit.py -q

# Or with uv
uv run python scripts/run_macd_td_v6_intake.py examples/pipeline_queries/macd_td_v6_intake.yaml
uv run pytest tests/research/test_macd_td_v6_intake.py tests/research/test_macd_td_v6_leakage_audit.py -q
```