from __future__ import annotations

import unittest

from quant_stack.intelligence.normalize import (
    basis_to_signal_events,
    liquidation_to_signal_events,
    normalize_symbol,
    normalize_timestamp,
)


class IntelligenceNormalizeTests(unittest.TestCase):
    def test_normalize_symbol(self) -> None:
        self.assertEqual(normalize_symbol("btc/usdt"), "BTC-USDT-SWAP")

    def test_basis_calculation_works(self) -> None:
        events = basis_to_signal_events(
            [{"symbol": "BTC-USDT", "timestamp": 1704067200000, "spot_price": 100.0, "perp_price": 101.0}]
        )
        self.assertAlmostEqual(events[0].value, 100.0)

    def test_liquidation_imbalance_works(self) -> None:
        events = liquidation_to_signal_events(
            [
                {
                    "symbol": "BTC-USDT",
                    "timestamp": 1704067200000,
                    "long_liquidation_notional": 300.0,
                    "short_liquidation_notional": 100.0,
                }
            ]
        )
        self.assertAlmostEqual(events[0].value, 0.5)

    def test_normalize_timestamp_ms(self) -> None:
        dt = normalize_timestamp(1704067200000)
        self.assertEqual(dt.year, 2024)


if __name__ == "__main__":
    unittest.main()
