"""Deterministic fixtures for the phase 17 pipeline harness."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import polars as pl

from quant_stack.data import validate_ohlcv
from quant_stack.intelligence.schemas import SignalEvent
from quant_stack.intelligence.store import DEFAULT_INTELLIGENCE_ROOT, load_events, save_events

DEFAULT_PHASE17_SYMBOL = "BTC-USDT-SWAP"
DEFAULT_PHASE17_TIMEFRAME = "1m"
DEFAULT_PHASE17_OHLCV_ROOT = Path("data/fixtures/phase17")
DEFAULT_PHASE17_OHLCV_FILENAME = "btc_usdt_swap_1m_ohlcv.parquet"
DEFAULT_PHASE17_START = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)


def build_phase17_btc_ohlcv_fixture(*, symbol: str = DEFAULT_PHASE17_SYMBOL, timeframe: str = DEFAULT_PHASE17_TIMEFRAME) -> pl.DataFrame:
    """Build a deterministic BTC OHLCV frame that satisfies validation."""

    closes = [100.0, 100.8, 101.4, 100.9, 102.2, 101.8, 103.1, 102.7, 103.6, 104.0, 103.4, 104.8]
    opens = [closes[0], *closes[:-1]]
    timestamps = pl.datetime_range(start=DEFAULT_PHASE17_START, end=DEFAULT_PHASE17_START.replace(minute=11), interval="1m", eager=True)
    frame = pl.DataFrame(
        {
            "timestamp": timestamps,
            "open": opens,
            "high": [max(open_value, close_value) + 0.4 for open_value, close_value in zip(opens, closes, strict=True)],
            "low": [min(open_value, close_value) - 0.4 for open_value, close_value in zip(opens, closes, strict=True)],
            "close": closes,
            "volume": [10.0, 11.0, 9.5, 12.0, 13.5, 12.5, 14.0, 13.0, 14.5, 15.0, 14.2, 15.8],
            "symbol": [symbol] * len(closes),
            "timeframe": [timeframe] * len(closes),
        }
    )
    return validate_ohlcv(frame)


def save_phase17_btc_ohlcv_fixture(
    *,
    root: str | Path = DEFAULT_PHASE17_OHLCV_ROOT,
    symbol: str = DEFAULT_PHASE17_SYMBOL,
    timeframe: str = DEFAULT_PHASE17_TIMEFRAME,
) -> Path:
    """Persist the deterministic BTC OHLCV fixture to parquet."""

    path = Path(root) / DEFAULT_PHASE17_OHLCV_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    build_phase17_btc_ohlcv_fixture(symbol=symbol, timeframe=timeframe).write_parquet(path)
    return path


def load_phase17_btc_ohlcv_fixture(path: str | Path) -> pl.DataFrame:
    """Load the deterministic BTC OHLCV fixture and re-validate it."""

    return validate_ohlcv(pl.read_parquet(path))


def build_phase17_intelligence_events(*, symbol: str = DEFAULT_PHASE17_SYMBOL) -> list[SignalEvent]:
    """Build deterministic mock intelligence events for the harness."""

    return [
        SignalEvent(
            source="liquidations",
            signal_type="liquidation_imbalance",
            symbol=symbol,
            timestamp=datetime(2024, 1, 1, 0, 2, tzinfo=timezone.utc),
            value=-0.75,
            metadata={"long_liquidation_notional": 25_000.0, "short_liquidation_notional": 175_000.0},
            historical_integrity=False,
        ),
        SignalEvent(
            source="okx_funding",
            signal_type="funding_rate",
            symbol=symbol,
            timestamp=datetime(2024, 1, 1, 0, 3, tzinfo=timezone.utc),
            value=0.00012,
            metadata={"next_funding_time": "2024-01-01T08:00:00Z"},
        ),
        SignalEvent(
            source="okx_basis",
            signal_type="basis_bps",
            symbol=symbol,
            timestamp=datetime(2024, 1, 1, 0, 4, tzinfo=timezone.utc),
            value=9.75,
            metadata={"spot_price": 101.2, "perp_price": 101.298},
        ),
        SignalEvent(
            source="okx_orderbook",
            signal_type="depth_imbalance",
            symbol=symbol,
            timestamp=datetime(2024, 1, 1, 0, 5, tzinfo=timezone.utc),
            value=0.25,
            metadata={"bid_depth": 240_000.0, "ask_depth": 144_000.0},
        ),
        SignalEvent(
            source="liquidations",
            signal_type="liquidation_imbalance",
            symbol=symbol,
            timestamp=datetime(2024, 1, 1, 0, 8, tzinfo=timezone.utc),
            value=0.5,
            metadata={"long_liquidation_notional": 150_000.0, "short_liquidation_notional": 50_000.0},
        ),
    ]


def save_phase17_intelligence_events(
    *,
    root: str | Path = DEFAULT_INTELLIGENCE_ROOT,
    symbol: str = DEFAULT_PHASE17_SYMBOL,
) -> list[Path]:
    """Persist the deterministic intelligence events through the event store."""

    return save_events(build_phase17_intelligence_events(symbol=symbol), root=root)


def load_phase17_intelligence_events(
    *,
    start: datetime,
    end: datetime,
    root: str | Path = DEFAULT_INTELLIGENCE_ROOT,
    symbol: str = DEFAULT_PHASE17_SYMBOL,
) -> pl.DataFrame:
    """Reload the deterministic intelligence events from parquet storage."""

    return load_events(symbol=symbol, start=start, end=end, root=root)


__all__ = [
    "DEFAULT_PHASE17_OHLCV_FILENAME",
    "DEFAULT_PHASE17_OHLCV_ROOT",
    "DEFAULT_PHASE17_START",
    "DEFAULT_PHASE17_SYMBOL",
    "DEFAULT_PHASE17_TIMEFRAME",
    "build_phase17_btc_ohlcv_fixture",
    "build_phase17_intelligence_events",
    "load_phase17_btc_ohlcv_fixture",
    "load_phase17_intelligence_events",
    "save_phase17_btc_ohlcv_fixture",
    "save_phase17_intelligence_events",
]
