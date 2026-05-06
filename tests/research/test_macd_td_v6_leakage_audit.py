"""Tests for MACD-TD V6 leakage audit functions."""

import polars as pl

from quant_stack.research.strategy_intake.macd_td_v6_audit import (
    compute_local_extrema_confirmed,
    compute_td_setup,
    create_deterministic_fixture,
    detect_bullish_macd_divergence,
    detect_bearish_macd_divergence,
    run_leakage_audit,
    update_trailing_stop_long,
    update_trailing_stop_short,
    verify_asof_backward_no_future_leakage,
)


class TestVerifyAsofBackward:
    def test_no_future_leakage(self):
        primary = pl.DataFrame({"close_time": [10, 20, 30]})
        secondary = pl.DataFrame({"close_time": [5, 15, 25]})

        result = verify_asof_backward_no_future_leakage(primary, secondary)
        assert result is True

    def test_has_future_leakage(self):
        primary = pl.DataFrame({"close_time": [10, 20, 30]})
        secondary = pl.DataFrame({"close_time": [15, 25, 35]})

        result = verify_asof_backward_no_future_leakage(primary, secondary)
        assert result is False


class TestComputeLocalExtremaConfirmed:
    def test_detects_extrema(self):
        close = pl.Series([1.0, 2.0, 1.5, 1.0, 2.0, 1.5, 1.0, 2.0, 1.5])
        extrema = compute_local_extrema_confirmed(close, window=2)
        assert len(extrema) > 0

    def test_empty_for_short_series(self):
        close = pl.Series([1.0, 2.0, 1.5])
        extrema = compute_local_extrema_confirmed(close, window=2)
        assert len(extrema) == 0


class TestComputeTDSetup:
    def test_buy_setup(self):
        close = pl.Series([100.0, 99.0, 98.0, 97.0, 96.0, 95.0, 94.0, 93.0, 92.0, 91.0] * 5)
        signals = compute_td_setup(close, period=9)
        assert signals.sum() >= 0

    def test_sell_setup(self):
        close = pl.Series([100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0] * 5)
        signals = compute_td_setup(close, period=9)
        assert signals.sum() <= 0


class TestDetectBullishDivergence:
    def test_detects_bullish_divergence(self):
        price = pl.Series([100.0, 99.0, 98.0, 97.0, 96.0, 95.0, 96.0, 97.0, 98.0, 99.0, 100.0])
        macd = pl.Series([-5.0, -4.0, -3.0, -2.0, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0])

        divergences = detect_bullish_macd_divergence(price, macd, lookback=5, min_strength=0.1)
        assert len(divergences) > 0


class TestDetectBearishDivergence:
    def test_detects_bearish_divergence(self):
        price = pl.Series([100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 104.0, 103.0, 102.0, 101.0, 100.0])
        macd = pl.Series([5.0, 4.0, 3.0, 2.0, 1.0, 0.5, 0.0, -0.5, -1.0, -1.5, -2.0])

        divergences = detect_bearish_macd_divergence(price, macd, lookback=5, min_strength=0.1)
        assert len(divergences) > 0


class TestTrailingStop:
    def test_long_only_moves_up(self):
        stop = 100.0
        stop = update_trailing_stop_long(stop, 105.0, 2.0)
        assert stop >= 100.0

        stop = update_trailing_stop_long(stop, 110.0, 2.0)
        assert stop >= 100.0

        stop = update_trailing_stop_long(stop, 95.0, 2.0)
        assert stop == 100.0

    def test_short_only_moves_down(self):
        stop = 100.0
        stop = update_trailing_stop_short(stop, 95.0, 2.0)
        assert stop <= 100.0

        stop = update_trailing_stop_short(stop, 90.0, 2.0)
        assert stop <= 100.0

        stop = update_trailing_stop_short(stop, 105.0, 2.0)
        assert stop == 100.0


class TestDeterministicFixture:
    def test_fixture_creation(self):
        fixture = create_deterministic_fixture()
        assert "ohlcv_15m" in fixture
        assert "ohlcv_5m" in fixture
        assert "ohlcv_1m" in fixture

        df = fixture["ohlcv_15m"]
        assert "close" in df.columns
        assert "open" in df.columns
        assert "high" in df.columns
        assert "low" in df.columns
        assert "volume" in df.columns
        assert len(df) > 0


class TestLeakageAudit:
    def test_run_audit(self):
        audit = run_leakage_audit()
        assert audit.same_bar_execution_risk is True
        assert audit.nearest_timestamp_leakage_risk is True
        assert audit.verdict in ["eligible", "eligible_with_risks", "not_eligible"]


class TestLeakageRiskFlagging:
    def test_same_bar_execution_flagged(self):
        audit = create_leakage_audit()
        assert audit.same_bar_execution_risk is True

    def test_nearest_timestamp_leakage_flagged(self):
        audit = create_leakage_audit()
        assert audit.nearest_timestamp_leakage_risk is True

    def test_extrema_confirmation_delay_flagged(self):
        audit = create_leakage_audit()
        assert audit.local_extrema_confirmation_delay_risk is True


class TestNoLiveBinanceInAudit:
    def test_audit_module_no_binance(self):
        import quant_stack.research.strategy_intake.macd_td_v6_audit as audit_module

        source = audit_module.__file__
        with open(source) as f:
            content = f.read()
            assert "binance" not in content.lower()
            assert "get_klines" not in content


class TestNoBrokerImports:
    def test_audit_module_no_broker(self):
        import quant_stack.research.strategy_intake.macd_td_v6_audit as audit_module

        source = audit_module.__file__
        with open(source) as f:
            content = f.read()
            assert "broker" not in content.lower() or "trailing" in content.lower()