import json
from pathlib import Path

import polars as pl

from quant_stack.strategies.smart_dca import SmartDCAParams
from quant_stack.strategies.smart_dca.backtester import SmartDCABacktester

DATA_PATH = Path("/root/quant-factory/XAU_1m_data.csv")
OUT_DIR = Path("artifacts/smart_dca_xau_v2")
OUT_DIR.mkdir(parents=True, exist_ok=True)

def main():
    if not DATA_PATH.exists():
        print(f"Data file not found: {DATA_PATH}")
        return

    print(f"Loading data from {DATA_PATH}")
    df = pl.read_csv(DATA_PATH, separator=";")
    
    print("Parsing timestamp...")
    # Format is "2004.06.11 07:18"
    df = df.with_columns(
        pl.col("Date").str.strptime(pl.Datetime, "%Y.%m.%d %H:%M").alias("timestamp")
    )
    
    print("Filtering 2020 to 2024...")
    df = df.filter(
        (pl.col("timestamp").dt.year() >= 2020) & (pl.col("timestamp").dt.year() <= 2024)
    )

    # Rename columns to lowercase to match expectations if any, though backtester accepts close_col
    df = df.rename({col: col.lower() for col in df.columns})

    print(f"Rows after filtering: {len(df)}")
    if len(df) == 0:
        print("No data in the specified range.")
        return

    print("\nConfiguring Backtester...")
    # Follow the original Smart DCA sizing explicitly
    params = SmartDCAParams(
        use_bid_as_avr=True,
        contract_size=1.0,
        commission_per_lot=0.0
    )
    # Enable all engines
    params.sb.enabled = True
    params.fb.enabled = True
    params.ss.enabled = True
    params.fs.enabled = True
    
    # Save run config
    with open(OUT_DIR / "run_config.json", "w") as f:
        f.write(params.model_dump_json(indent=2))

    backtester = SmartDCABacktester(
        initial_capital=10000.0,
        timestamp_col="timestamp",
        close_col="close"
    )

    print("Running Backtest via SmartDCABacktester...")
    result = backtester.run(df, params)
    print("Backtest finished.")

    print("\n--- Metrics ---")
    print(json.dumps(result.metrics, indent=2))

    # Save summary
    with open(OUT_DIR / "summary.json", "w") as f:
        json.dump(result.metrics, f, indent=2)

    # Save frame
    result.frame.write_parquet(OUT_DIR / "equity_curve.parquet")
    print(f"Artifacts saved to {OUT_DIR}")

if __name__ == "__main__":
    main()
