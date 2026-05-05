from __future__ import annotations

import unittest
from datetime import datetime, timezone

from quant_stack.intelligence.schemas import BasisSignal, FundingSignal, MarketContextSnapshot, SignalEvent


class IntelligenceSchemaTests(unittest.TestCase):
    def test_signal_event_validates(self) -> None:
        event = SignalEvent(
            source="okx",
            signal_type="funding_rate",
            symbol="BTC-USDT-SWAP",
            timestamp=datetime.now(timezone.utc),
            value=0.0001,
        )
        self.assertEqual(event.signal_type, "funding_rate")

    def test_snapshot_schema(self) -> None:
        snap = MarketContextSnapshot(symbol="BTC-USDT-SWAP", timestamp=datetime.now(timezone.utc), funding_rate=0.0001)
        self.assertEqual(snap.symbol, "BTC-USDT-SWAP")

    def test_basis_signal_schema(self) -> None:
        basis = BasisSignal(
            symbol="BTC-USDT-SWAP",
            timestamp=datetime.now(timezone.utc),
            spot_price=100.0,
            perp_price=101.0,
            basis=1.0,
            basis_bps=100.0,
        )
        self.assertEqual(basis.basis_bps, 100.0)


if __name__ == "__main__":
    unittest.main()
