"""
engine/deps.py
Centralized Dependency Injection container for the Quant Factory.
Holds persistent DuckDB connection and CCXT exchange client.
One connection is created, injected into every agent, and reused forever.
"""
import duckdb
import ccxt
import numpy as np
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class QuantFactoryDeps:
    """
    The single source of truth injected into every agent via RunContext.
    Never recreate these clients inside an agent tool — always use this.
    """
    db: duckdb.DuckDBPyConnection
    exchange: ccxt.binance

    def load_multi_year(
        self,
        asset: str = "ETH",
        years: list[int] = None,
        split_date: str = None
    ) -> tuple[np.ndarray, np.ndarray, object, object]:
        """
        Queries across multiple Parquet files via DuckDB glob in one shot.
        Returns (train_close, test_close, train_df_polars, test_df_polars).

        Args:
            asset: 'BTC' or 'ETH'
            years: list of years to include e.g. [2021, 2022, 2023]
            split_date: ISO string to split train/test e.g. '2023-01-01'
        """
        import polars as pl

        if years is None:
            years = [2021, 2022, 2023, 2024]
        if split_date is None:
            split_date = f"{years[-1]}-07-01"

        # Build a glob that covers only the requested years
        file_patterns = [
            f"'Data/Binance/{asset}_1m_{y}.parquet'" for y in years
        ]
        union_query = " UNION ALL ".join(
            [f"SELECT datetime as timestamp, close FROM read_parquet({p})" for p in file_patterns]
        )
        query = f"""
            SELECT timestamp, close 
            FROM ({union_query})
            ORDER BY timestamp ASC
        """
        raw_df = self.db.sql(query).pl()

        split_dt = pl.datetime(*[int(x) for x in split_date.split("-")])
        train_df = raw_df.filter(pl.col("timestamp") < split_dt)
        test_df = raw_df.filter(pl.col("timestamp") >= split_dt)

        return (
            train_df["close"].to_numpy(),
            test_df["close"].to_numpy(),
            train_df,
            test_df
        )

    def get_orderbook_snapshot(self, symbol: str = "ETH/USDT", depth: int = 20) -> dict:
        """
        Fetches a live orderbook from Binance via the persistent CCXT client.
        Returns bid_wall, ask_wall, spread_pct.
        """
        ob = self.exchange.fetch_order_book(symbol, limit=depth)
        bid_wall = sum(b[1] for b in ob["bids"])
        ask_wall = sum(a[1] for a in ob["asks"])
        best_bid = ob["bids"][0][0]
        best_ask = ob["asks"][0][0]
        spread_pct = ((best_ask - best_bid) / best_bid) * 100

        return {
            "symbol": symbol,
            "bid_wall_qty": round(bid_wall, 4),
            "ask_wall_qty": round(ask_wall, 4),
            "spread_pct": round(spread_pct, 5),
            "best_bid": best_bid,
            "best_ask": best_ask,
        }

    def get_recent_trades(self, symbol: str = "ETH/USDT", limit: int = 100) -> dict:
        """
        Fetches recent trades to assess short-term momentum.
        """
        trades = self.exchange.fetch_trades(symbol, limit=limit)
        buys = sum(1 for t in trades if t["side"] == "buy")
        sells = limit - buys
        buy_vol = sum(t["amount"] for t in trades if t["side"] == "buy")
        sell_vol = sum(t["amount"] for t in trades if t["side"] == "sell")
        return {
            "buy_count": buys,
            "sell_count": sells,
            "buy_volume": round(buy_vol, 4),
            "sell_volume": round(sell_vol, 4),
            "buy_pressure_pct": round((buys / limit) * 100, 1),
        }


def create_deps(data_dir: str = "Data/Binance") -> QuantFactoryDeps:
    """
    Factory function. Call once at startup, pass the result everywhere.
    """
    print("🔌 Connecting to DuckDB (persistent session)...")
    db = duckdb.connect()

    print("🔌 Authenticating CCXT Binance client (rate-limit enabled)...")
    exchange = ccxt.binance({"enableRateLimit": True})

    return QuantFactoryDeps(db=db, exchange=exchange)
