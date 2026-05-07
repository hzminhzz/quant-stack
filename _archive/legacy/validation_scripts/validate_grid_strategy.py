"""DEPRECATED legacy validation entrypoint.

This script is kept for compatibility/reference and should not be used as the
default model for new canonical validation workflows.
"""

import glob
import numpy as np
import polars as pl

from engine.grid_backtester import calculate_grid_metrics, simulate_dynamic_grid


def load_eth_data():
    files = glob.glob("Data/Binance/ETH_1m_2026.parquet")
    if not files:
        raise FileNotFoundError("No ETH 1m data found in Data/Binance/")

    print(f"Found {len(files)} data files. Loading...")
    dfs = [pl.read_parquet(f) for f in files]
    df = pl.concat(dfs).sort("timestamp")
    return df


def main():
    print("--- Dynamic Boundary Chase Grid Validation ---")

    try:
        df = load_eth_data()
        print(f"Loaded {len(df)} rows of ETH data.")
    except Exception as e:
        print(f"Error loading data: {e}")
        return

    close_prices = df["close"].to_numpy().astype(np.float64)

    num_levels = 10
    grid_width_pct = 0.20
    fee_pct = 0.0002

    print(f"Simulating Grid: Levels={num_levels}, Width={grid_width_pct*100}%, Fees={fee_pct*100}%")

    equity_curve = simulate_dynamic_grid(
        close_prices,
        num_levels=num_levels,
        grid_width_pct=grid_width_pct,
        fee_pct=fee_pct,
    )

    metrics = calculate_grid_metrics(equity_curve)

    print("\n--- Backtest Results ---")
    for k, v in metrics.items():
        if "Return" in k or "Drawdown" in k:
            print(f"{k}: {v*100:.2f}%")
        else:
            print(f"{k}: {v:.4f}")

    df_results = df.with_columns(pl.Series("equity", equity_curve))
    output_path = "Data/grid_backtest_results.parquet"
    df_results.write_parquet(output_path)
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    main()
