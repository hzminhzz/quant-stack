from __future__ import annotations

import unittest
from datetime import datetime, timezone

import polars as pl

from quant_stack.intelligence.regime_context import apply_context_gate_to_signals


class RegimeContextGateTests(unittest.TestCase):
    def test_raw_signal_equals_pre_gating_signal(self) -> None:
        signal_frame = pl.DataFrame(
            {
                "timestamp": [
                    datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
                    datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
                    datetime(2024, 1, 1, 2, 0, tzinfo=timezone.utc),
                ],
                "close": [100.0, 101.0, 102.0],
                "signal": [None, 1, None],
            }
        )
        context_frame = pl.DataFrame(
            {
                "timestamp": [datetime(2024, 1, 1, 0, 30, tzinfo=timezone.utc)],
                "spread_bps": [5.0],
            }
        )

        gated = apply_context_gate_to_signals(signal_frame, context_frame, max_spread_bps=20.0)
        self.assertListEqual(signal_frame.get_column("signal").to_list(), gated.get_column("raw_signal").to_list())

    def test_spread_threshold_suppresses_only_failing_entries(self) -> None:
        signal_frame = pl.DataFrame(
            {
                "timestamp": [
                    datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
                    datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
                    datetime(2024, 1, 1, 2, 0, tzinfo=timezone.utc),
                    datetime(2024, 1, 1, 3, 0, tzinfo=timezone.utc),
                ],
                "close": [100.0, 101.0, 102.0, 103.0],
                "signal": [None, 1, 0, 1],
            }
        )
        context_frame = pl.DataFrame(
            {
                "timestamp": [
                    datetime(2024, 1, 1, 0, 30, tzinfo=timezone.utc),
                    datetime(2024, 1, 1, 2, 30, tzinfo=timezone.utc),
                ],
                "spread_bps": [10.0, 50.0],
            }
        )

        gated = apply_context_gate_to_signals(signal_frame, context_frame, max_spread_bps=20.0)
        # 01:00 sees spread=10 (pass), 03:00 sees spread=50 (fail).
        self.assertEqual(gated.get_column("signal").to_list(), [None, 1, 0, None])
        self.assertEqual(gated.get_column("context_gate_pass").to_list(), [True, True, True, False])

    def test_missing_context_can_remain_permissive(self) -> None:
        signal_frame = pl.DataFrame(
            {
                "timestamp": [
                    datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
                    datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
                ],
                "close": [100.0, 101.0],
                "signal": [1, 1],
            }
        )
        context_frame = pl.DataFrame({"timestamp": [], "spread_bps": []})

        gated = apply_context_gate_to_signals(
            signal_frame,
            context_frame,
            max_spread_bps=20.0,
            suppress_when_context_missing=False,
        )
        self.assertEqual(gated.get_column("signal").to_list(), [1, 1])
        self.assertEqual(gated.get_column("context_gate_pass").to_list(), [True, True])


if __name__ == "__main__":
    unittest.main()
