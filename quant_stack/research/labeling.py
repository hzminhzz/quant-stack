"""Research-layer deterministic labeling helpers.

WARNING: Triple-barrier labels are future-looking targets by design.
They are valid for offline research/training only and MUST NOT be consumed
as live/backtest decision features at the same timestamp.

Implements a compact triple-barrier labeling variant for experiment workflows.
"""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl


@dataclass(frozen=True)
class TripleBarrierConfig:
    profit_take_pct: float
    stop_loss_pct: float
    max_holding_bars: int
    include_barrier_hit: bool = True
    time_col: str = "timestamp"
    price_col: str = "close"
    high_col: str | None = "high"
    low_col: str | None = "low"
    group_col: str | None = None
    side_col: str | None = None

    def __post_init__(self) -> None:
        if self.profit_take_pct <= 0:
            raise ValueError("profit_take_pct must be positive")
        if self.stop_loss_pct <= 0:
            raise ValueError("stop_loss_pct must be positive")
        if self.max_holding_bars <= 0:
            raise ValueError("max_holding_bars must be positive")


def triple_barrier_labels(df: pl.DataFrame, config: TripleBarrierConfig) -> pl.DataFrame:
    """Return a labeled copy of ``df`` for research targets.

    This function does not mutate ``df``.
    """
    _require_columns(df, [config.time_col, config.price_col])
    if config.high_col is not None:
        _require_columns(df, [config.high_col])
    if config.low_col is not None:
        _require_columns(df, [config.low_col])
    if config.side_col is not None:
        _require_columns(df, [config.side_col])

    sorted_df = _sorted(df, config)
    groups = _split_groups(sorted_df, config.group_col)
    labeled_parts: list[pl.DataFrame] = []
    for part in groups:
        labeled_parts.append(_label_group(part, config))
    return pl.concat(labeled_parts) if labeled_parts else sorted_df


def _split_groups(df: pl.DataFrame, group_col: str | None) -> list[pl.DataFrame]:
    if group_col is None:
        return [df]
    return [sub for _, sub in df.group_by(group_col, maintain_order=True)]


def _sorted(df: pl.DataFrame, config: TripleBarrierConfig) -> pl.DataFrame:
    sort_cols = [config.time_col] if config.group_col is None else [config.group_col, config.time_col]
    return df.sort(sort_cols)


def _label_group(df: pl.DataFrame, config: TripleBarrierConfig) -> pl.DataFrame:
    rows = df.to_dicts()
    n = len(rows)

    labels: list[int] = []
    label_time: list[object] = []
    label_price: list[float] = []
    label_return: list[float] = []
    label_bars: list[int] = []
    barrier_hit: list[str] = []

    for i in range(n):
        entry_price = float(rows[i][config.price_col])
        side = float(rows[i][config.side_col]) if config.side_col is not None else 1.0
        if side == 0.0:
            side = 1.0
        up_mult = 1.0 + config.profit_take_pct
        dn_mult = 1.0 - config.stop_loss_pct
        pt_level = entry_price * up_mult
        sl_level = entry_price * dn_mult

        exit_idx = min(i + config.max_holding_bars, n - 1)
        hit = "time"
        out_label = 0
        out_return = 0.0
        out_price = float(rows[exit_idx][config.price_col])

        for j in range(i + 1, min(i + config.max_holding_bars, n - 1) + 1):
            high = float(rows[j][config.high_col]) if config.high_col is not None else float(rows[j][config.price_col])
            low = float(rows[j][config.low_col]) if config.low_col is not None else float(rows[j][config.price_col])

            if side > 0:
                if high >= pt_level:
                    exit_idx = j
                    out_price = pt_level
                    out_return = (out_price / entry_price) - 1.0
                    out_label = 1
                    hit = "profit_take"
                    break
                if low <= sl_level:
                    exit_idx = j
                    out_price = sl_level
                    out_return = (out_price / entry_price) - 1.0
                    out_label = -1
                    hit = "stop_loss"
                    break
            else:
                if low <= entry_price * (1.0 - config.profit_take_pct):
                    exit_idx = j
                    out_price = entry_price * (1.0 - config.profit_take_pct)
                    out_return = (entry_price / out_price) - 1.0
                    out_label = 1
                    hit = "profit_take"
                    break
                if high >= entry_price * (1.0 + config.stop_loss_pct):
                    exit_idx = j
                    out_price = entry_price * (1.0 + config.stop_loss_pct)
                    out_return = (entry_price / out_price) - 1.0
                    out_label = -1
                    hit = "stop_loss"
                    break

        if hit == "time":
            final_price = float(rows[exit_idx][config.price_col])
            if side > 0:
                out_return = (final_price / entry_price) - 1.0
            else:
                out_return = (entry_price / final_price) - 1.0
            out_label = 1 if out_return > 0 else (-1 if out_return < 0 else 0)
            out_price = final_price

        labels.append(out_label)
        label_time.append(rows[exit_idx][config.time_col])
        label_price.append(float(out_price))
        label_return.append(float(out_return))
        label_bars.append(int(exit_idx - i))
        barrier_hit.append(hit)

    out = df.with_columns(
        [
            pl.Series("label", labels),
            pl.Series("label_time", label_time),
            pl.Series("label_price", label_price),
            pl.Series("label_return", label_return),
            pl.Series("label_bars", label_bars),
        ]
    )
    if config.include_barrier_hit:
        out = out.with_columns(pl.Series("barrier_hit", barrier_hit))
    return out


def _require_columns(df: pl.DataFrame, cols: list[str]) -> None:
    missing = [col for col in cols if col not in df.columns]
    if missing:
        raise ValueError(f"missing required columns: {', '.join(missing)}")


__all__ = ["TripleBarrierConfig", "triple_barrier_labels"]
