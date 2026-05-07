"""
validate_bb_strategy.py
Specialized 4-Hour Bollinger Band Strategy Validator.
Resamples 1m data to 4h and runs the 3-phase GAUNTLET.

DEPRECATED: legacy validation entrypoint. Kept for compatibility/reference.
Do not use this as the default model for new canonical workflow development.
"""
import argparse
import asyncio
import numpy as np
import polars as pl
import os
from engine.backtester_bb import get_equity_and_trades_bb
from engine.analytics_pro import calculate_prop_metrics
from engine.monte_carlo import run_monte_carlo
from engine.deps import create_deps


def resample_4h(df: pl.DataFrame) -> pl.DataFrame:
    """Resample 1m data to 4h OHLCV."""
    if 'datetime' not in df.columns:
        df = df.with_columns(pl.from_epoch("timestamp", time_unit="ms").alias("datetime"))

    return (
        df.sort("datetime")
        .group_by_dynamic("datetime", every="4h")
        .agg([
            pl.col("open").first(),
            pl.col("high").max(),
            pl.col("low").min(),
            pl.col("close").last(),
            pl.col("volume").sum()
        ])
        .rename({"datetime": "timestamp"})
    )


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset", default="BTC")
    parser.add_argument("--train-years", nargs="+", type=int, default=[2018, 2019, 2020, 2021, 2022, 2023])
    parser.add_argument("--test-years", nargs="+", type=int, default=[2024, 2025, 2026])
    args = parser.parse_args()

    print(f"\n{'='*70}\n  GAUNTLET: BOLLINGER BAND BREAKOUT (4H)\n{'='*70}")
    deps = create_deps()

    print(f"📂 Loading and resampling {args.asset} 1m data to 4h...")

    def load_years(asset, years):
        file_patterns = [f"'Data/Binance/{asset}_1m_{y}.parquet'" for y in years]
        valid_files = [p for p in file_patterns if os.path.exists(p.strip("'"))]
        if not valid_files:
            return None

        union_query = " UNION ALL ".join([f"SELECT * FROM read_parquet({p})" for p in valid_files])
        query = f"SELECT * FROM ({union_query}) ORDER BY timestamp ASC"
        return deps.db.sql(query).pl()

    train_raw = load_years(args.asset, args.train_years)
    test_raw = load_years(args.asset, args.test_years)

    if train_raw is None or test_raw is None:
        print("❌ Error: Missing Parquet data for the requested years.")
        return

    train_4h = resample_4h(train_raw)
    test_4h = resample_4h(test_raw)

    train_close = train_4h["close"].to_numpy()
    test_close = test_4h["close"].to_numpy()

    print(f"  -> In-Sample:  {len(train_4h)} bars (4H)")
    print(f"  -> Out-Sample: {len(test_4h)} bars (4H)")

    print(f"\n⚙️  [Phase 1]: In-Sample Backtest ({args.train_years})...")
    equity, exposed, trades = get_equity_and_trades_bb(
        train_close, bb_length=20, bb_std=1.0, regime_sma_length=200, friction=0.0015
    )

    is_df = train_4h.with_columns([
        pl.Series("equity", equity) * 10000.0,
        pl.Series("is_exposed", exposed)
    ])

    metrics = calculate_prop_metrics(is_df, initial_capital=10000.0)
    print("\n📊 [In-Sample] Metrics")
    for k, v in metrics.items():
        print(f"  ├─ {k:15}: {v:>10.4f}" if isinstance(v, float) else f"  ├─ {k:15}: {v:>10}")

    print(f"\n🎲 [Phase 2]: Monte Carlo Stress Test (1,000 shuffles)...")
    mc_95, mc_50 = run_monte_carlo(trades, num_simulations=1000)
    print(f"  -> 95th Percentile Worst-Case DD: {mc_95 * 100:.2f}%")

    print(f"\n🔮 [Phase 3]: Out-Of-Sample Backtest ({args.test_years})...")
    equity_oos, exposed_oos, trades_oos = get_equity_and_trades_bb(
        test_close, bb_length=20, bb_std=1.0, regime_sma_length=200, friction=0.0015
    )

    oos_df = test_4h.with_columns([
        pl.Series("equity", equity_oos) * 10000.0,
        pl.Series("is_exposed", exposed_oos)
    ])

    metrics_oos = calculate_prop_metrics(oos_df, initial_capital=10000.0)
    print("\n📊 [Out-Of-Sample] Metrics")
    for k, v in metrics_oos.items():
        print(f"  ├─ {k:15}: {v:>10.4f}" if isinstance(v, float) else f"  ├─ {k:15}: {v:>10}")

    print(f"\n  ✅ TOTAL TRADES (IS):  {len(trades)}")
    print(f"  ✅ TOTAL TRADES (OOS): {len(trades_oos)}")

    deps.db.close()


if __name__ == "__main__":
    asyncio.run(main())
