## 2026-05-05
- The original Phase 17 checked-in examples were producing flat or no-delta artifacts because the 1h synthetic fixture path was effectively flat and the 1m path never produced an RSI entry under default strategy params.
- A deterministic 1m piecewise path with a deep drawdown, short recovery, and a tiny profitable exit window produces a baseline RSI trade while preserving candidate suppression through context gating.
- A deterministic 1h path with stronger upward drift (`0.07 * index`) and smaller periodic pulses (`3.0`) restores profitable `bb_breakout` baseline/candidate runs without touching strategy formulas or backtester semantics.
- Modeling the optional optimization artifact as `OptimizationRequestRecord` gives the harness an explicit `status: proposed` state instead of a bare `OptimizationRequest` payload, while still avoiding any queue worker execution.
- Repeated runs were made stable by normalizing manifest path fields to relative names and leaving the manifest timestamp as `null`; repeated-run equality checks passed for both example manifests and both proposed optimization artifacts.
