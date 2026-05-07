import json
from pathlib import Path

import numpy as np
import polars as pl

from quant_stack.strategies.smart_dca import SmartDCAParams, run_smart_dca_backtest


DATA_PATH = Path("/root/quant-factory/data/XAUUSD.parquet")
OUT_DIR = Path("artifacts/smart_dca_xauusd")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    if not DATA_PATH.exists():
        print(f"Data file not found: {DATA_PATH}")
        return

    print(f"Loading data from {DATA_PATH}")
    df = pl.read_parquet(DATA_PATH)

    print("\n--- DataFrame Info ---")
    print("Shape:", df.shape)
    print("Columns:", df.columns)
    print("\nHead(5):")
    print(df.head(5))
    print("\nTail(5):")
    print(df.tail(5))
    print("\nNull counts:")
    print(df.null_count())

    # Detect timestamp column
    time_col = None
    for candidate in ["timestamp", "time", "datetime", "date", "open_time"]:
        if candidate in df.columns:
            time_col = candidate
            break
        elif candidate.capitalize() in df.columns:
            time_col = candidate.capitalize()
            break
            
    if time_col is None:
        print("Warning: No timestamp column found. Falling back to index-based timestamps.")
        time_col = "timestamp"
        df = df.with_columns(
            (pl.Series(np.arange(len(df), dtype="timedelta64[ms]")) + np.datetime64("2020-01-01T00:00:00")).alias(time_col)
        )
        used_time_mode = "index_fallback"
    else:
        dt_type = df.schema[time_col]
        print(f"\nTimestamp column detected: {time_col} of type {dt_type}")
        if dt_type == pl.String and "Date" in df.columns:
            print("Parsing Date and Timestamp strings into a Datetime column...")
            df = df.with_columns(
                (pl.col("Date").cast(pl.Utf8) + " " + pl.col(time_col)).str.strptime(pl.Datetime, "%Y%m%d %H:%M:%S").alias("parsed_timestamp")
            )
            time_col = "parsed_timestamp"
            used_time_mode = "parsed_date_time"
        else:
            used_time_mode = f"column_{time_col}"

    # Detect price columns
    bid_col, ask_col = None, None
    used_bid_ask_mode = ""
    
    col_lower = {c.lower(): c for c in df.columns}
    
    if "bid" in col_lower and "ask" in col_lower:
        bid_col = col_lower["bid"]
        ask_col = col_lower["ask"]
        used_bid_ask_mode = "bid_ask"
    elif "close" in col_lower and "spread" in col_lower:
        close_c = col_lower["close"]
        spread_c = col_lower["spread"]
        bid_col = "bid"
        ask_col = "ask"
        df = df.with_columns(
            pl.col(close_c).alias(bid_col),
            (pl.col(close_c) + pl.col(spread_c)).alias(ask_col)
        )
        used_bid_ask_mode = "close_spread"
    elif "close" in col_lower:
        close_c = col_lower["close"]
        bid_col = "bid"
        ask_col = "ask"
        df = df.with_columns(
            pl.col(close_c).alias(bid_col),
            pl.col(close_c).alias(ask_col)
        )
        used_bid_ask_mode = "close_only"
        print("Warning: close-only fallback used; spread ignored")
    else:
        raise ValueError(f"Could not detect valid price columns among: {df.columns}")

    print(f"\nUsing bid/ask mode: {used_bid_ask_mode} with columns {bid_col}, {ask_col}")

    # Drop nulls to prevent NaN propagation
    df = df.drop_nulls(subset=[bid_col, ask_col])

    # Configure Strategy
    params = SmartDCAParams(
        use_bid_as_avr=True,
        contract_size=100.0,  # Standard lot for XAUUSD is 100 oz
        commission_per_lot=0.0
    )
    
    # Save run config
    with open(OUT_DIR / "run_config.json", "w") as f:
        f.write(params.model_dump_json(indent=2))

    print("\nRunning Smart DCA backtest...")
    result = run_smart_dca_backtest(
        df=df,
        cfg=params,
        time_col=time_col,
        bid_col=bid_col,
        ask_col=ask_col
    )
    print("Backtest finished.")

    INITIAL_EQUITY = 10000.0
    equity_curve = result["equity"] + INITIAL_EQUITY
    
    # Save outputs
    # 1. Equity curve
    equity_df = pl.DataFrame({
        "timestamp": df[time_col],
        "equity": equity_curve,
        "realized_pnl": result["realized_pnl"],
        "open_pnl": result["open_pnl"],
        "net_lot": result["net_lot"]
    })
    equity_df.write_parquet(OUT_DIR / "equity_curve.parquet")
    
    # 2. Trades
    if len(result["trade_time_idx"]) > 0:
        trades_df = pl.DataFrame({
            "timestamp": df[time_col][result["trade_time_idx"]],
            "engine": result["trade_engine"],
            "side": result["trade_side"],
            "action": result["trade_action"],
            "price": result["trade_price"],
            "lot": result["trade_lot"],
            "reason": result["trade_reason"]
        })
        trades_df.write_parquet(OUT_DIR / "trades.parquet")
    else:
        trades_df = pl.DataFrame()
        print("No trades executed.")

    # Calculate metrics
    n_trades = int(len(trades_df))
    n_open = int(sum(result["trade_action"] == 1)) if n_trades > 0 else 0
    n_close = int(sum(result["trade_action"] == -1)) if n_trades > 0 else 0
    
    final_equity = float(equity_curve[-1]) if len(equity_curve) > 0 else INITIAL_EQUITY
    total_realized_pnl = float(result["realized_pnl"][-1]) if len(result["realized_pnl"]) > 0 else 0.0
    
    # Max Drawdown
    peaks = np.maximum.accumulate(equity_curve)
    drawdowns_abs = peaks - equity_curve
    max_drawdown_abs = float(np.max(drawdowns_abs)) if len(drawdowns_abs) > 0 else 0.0
    
    drawdowns_pct = drawdowns_abs / np.where(peaks > 0, peaks, 1.0)
    max_drawdown_pct = float(np.max(drawdowns_pct)) if len(drawdowns_pct) > 0 else 0.0

    # Profit Factor
    realized_diff = np.diff(result["realized_pnl"], prepend=0.0)
    gross_profit = float(np.sum(realized_diff[realized_diff > 0]))
    gross_loss = float(np.abs(np.sum(realized_diff[realized_diff < 0])))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Sharpe Ratio
    if len(equity_curve) > 1:
        returns = np.diff(equity_curve) / equity_curve[:-1]
        trading_minutes_per_year = 252 * 24 * 60
        std_ret = np.std(returns)
        sharpe_ratio = float(np.mean(returns) / std_ret * np.sqrt(trading_minutes_per_year)) if std_ret > 0 else 0.0
    else:
        sharpe_ratio = 0.0

    first_trade_time = str(trades_df["timestamp"][0]) if n_trades > 0 else None
    last_trade_time = str(trades_df["timestamp"][-1]) if n_trades > 0 else None

    summary = {
        "rows": len(df),
        "start_time": str(df[time_col][0]) if len(df) > 0 else None,
        "end_time": str(df[time_col][-1]) if len(df) > 0 else None,
        "number_of_trades": n_trades,
        "number_of_open_events": n_open,
        "number_of_close_events": n_close,
        "initial_equity": INITIAL_EQUITY,
        "final_equity": final_equity,
        "total_realized_pnl": total_realized_pnl,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": profit_factor,
        "max_drawdown_abs": max_drawdown_abs,
        "max_drawdown_pct": max_drawdown_pct,
        "sharpe_ratio": sharpe_ratio,
        "first_trade_time": first_trade_time,
        "last_trade_time": last_trade_time,
        "used_bid_ask_mode": used_bid_ask_mode,
        "warnings": []
    }

    if n_trades < 30:
        msg = "Low trade count; performance metrics are statistically weak."
        print(f"Warning: {msg}")
        summary["warnings"].append(msg)

    with open(OUT_DIR / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)
        
    print(f"\nArtifacts saved to {OUT_DIR}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
