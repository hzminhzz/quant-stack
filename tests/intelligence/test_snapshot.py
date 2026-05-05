from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

from quant_stack.intelligence.schemas import SignalEvent
from quant_stack.intelligence.snapshot import build_context_snapshot, join_context_to_trades
from quant_stack.intelligence.store import save_events


class IntelligenceSnapshotTests(unittest.TestCase):
    def test_snapshot_uses_latest_available_at_time_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            events = [
                SignalEvent(
                    source="okx_funding",
                    signal_type="funding_rate",
                    symbol="BTC-USDT-SWAP",
                    timestamp=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
                    value=0.001,
                ),
                SignalEvent(
                    source="okx_funding",
                    signal_type="funding_rate",
                    symbol="BTC-USDT-SWAP",
                    timestamp=datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
                    value=0.002,
                ),
            ]
            save_events(events, root=root)
            snap = build_context_snapshot("BTC-USDT-SWAP", datetime(2024, 1, 1, 0, 30, tzinfo=timezone.utc), root=root.as_posix())
            self.assertAlmostEqual(float(snap.funding_rate or 0.0), 0.001)

    def test_future_only_signal_rejected_for_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            events = [
                SignalEvent(
                    source="liquidations",
                    signal_type="liquidation_imbalance",
                    symbol="BTC-USDT-SWAP",
                    timestamp=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
                    value=0.5,
                    historical_integrity=False,
                )
            ]
            save_events(events, root=root)
            snap = build_context_snapshot("BTC-USDT-SWAP", datetime(2024, 1, 1, 0, 30, tzinfo=timezone.utc), root=root.as_posix())
            self.assertIsNone(snap.liquidation_imbalance)

    def test_join_context_to_trades_no_future_leak(self) -> None:
        trades = pl.DataFrame(
            {
                "timestamp": [
                    datetime(2024, 1, 1, 0, 30, tzinfo=timezone.utc),
                    datetime(2024, 1, 1, 1, 30, tzinfo=timezone.utc),
                ],
                "pnl": [1.0, -1.0],
            }
        )
        context = pl.DataFrame(
            {
                "timestamp": [
                    datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
                    datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
                ],
                "funding_rate": [0.001, 0.002],
            }
        )
        joined = join_context_to_trades(trades, context)
        self.assertAlmostEqual(float(joined["funding_rate"][0]), 0.001)
        self.assertAlmostEqual(float(joined["funding_rate"][1]), 0.002)


if __name__ == "__main__":
    unittest.main()
