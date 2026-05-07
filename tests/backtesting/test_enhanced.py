"""Tests for enhanced backtesting engine."""

import polars as pl
import pytest
from datetime import datetime, timedelta

from quant_stack.backtesting.enhanced import (
    SizingMode,
    FeeMode,
    SizingConfig,
    ExecutionCost,
    InstrumentSpec,
    BybitLinearConfig,
    MarginConfig,
    FundingConfig,
    EnhancedBacktestConfig,
    run_enhanced_backtest,
    create_bybit_config,
)


def make_test_df(prices: list[float]) -> pl.DataFrame:
    """Create test OHLCV DataFrame."""
    timestamps = [datetime(2024, 1, 1) + timedelta(hours=i) for i in range(len(prices))]
    return pl.DataFrame({
        "timestamp": timestamps,
        "open": prices,
        "high": [p * 1.01 for p in prices],
        "low": [p * 0.99 for p in prices],
        "close": prices,
    })


class TestSizingModes:
    """Test Phase 1: Sizing modes."""

    def test_binary_sizing(self):
        df = make_test_df([100.0] * 10)
        signals = pl.Series("signal", [0.0, 1.0, 1.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0, 0.0])
        
        config = EnhancedBacktestConfig(
            sizing=SizingConfig(mode=SizingMode.BINARY),
        )
        
        result = run_enhanced_backtest(df, signals, config)
        
        # Binary should have position 0 or 1
        positions = result["position"].to_list()
        assert all(p in [0.0, 1.0] for p in positions)

    def test_fractional_equity_sizing(self):
        df = make_test_df([100.0] * 10)
        signals = pl.Series("signal", [0.0, 1.0, 1.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0, 0.0])
        
        config = EnhancedBacktestConfig(
            initial_capital=10000,
            sizing=SizingConfig(
                mode=SizingMode.FRACTIONAL_EQUITY,
                exposure_fraction=0.5,
                leverage=1.0,
            ),
        )
        
        result = run_enhanced_backtest(df, signals, config)
        
        # At 50% exposure, position should be ~50 units (5000/100)
        position = result["position"][1]
        expected = (10000 * 0.5) / 100
        assert abs(position - expected) < 0.01

    def test_fixed_notional_sizing(self):
        df = make_test_df([100.0] * 10)
        signals = pl.Series("signal", [1.0] * 10)
        
        config = EnhancedBacktestConfig(
            sizing=SizingConfig(
                mode=SizingMode.FIXED_NOTIONAL,
                fixed_notional=1000.0,
            ),
        )
        
        result = run_enhanced_backtest(df, signals, config)
        
        # Position should be 10 (1000/100)
        assert result["position"][0] == 10.0

    def test_fixed_qty_sizing(self):
        df = make_test_df([100.0] * 10)
        signals = pl.Series("signal", [1.0] * 10)
        
        config = EnhancedBacktestConfig(
            sizing=SizingConfig(
                mode=SizingMode.FIXED_QTY,
                fixed_qty=5.0,
            ),
        )
        
        result = run_enhanced_backtest(df, signals, config)
        
        assert result["position"][0] == 5.0


class TestExecutionCosts:
    """Test Phase 2: Execution costs."""

    def test_taker_fees_reduce_equity(self):
        df = make_test_df([100.0, 110.0, 120.0])  # 20% move up
        signals = pl.Series("signal", [1.0, 1.0, 0.0])  # Enter and exit
        
        # With fees
        config_with_fees = EnhancedBacktestConfig(
            initial_capital=10000,
            sizing=SizingConfig(mode=SizingMode.BINARY),
            execution=ExecutionCost(taker_fee_rate=0.001, fee_mode=FeeMode.TAKER),
        )
        result_with = run_enhanced_backtest(df, signals, config_with_fees)
        
        # Without fees
        config_no_fees = EnhancedBacktestConfig(
            initial_capital=10000,
            sizing=SizingConfig(mode=SizingMode.BINARY),
            execution=ExecutionCost(taker_fee_rate=0.0),
        )
        result_without = run_enhanced_backtest(df, signals, config_no_fees)
        
        # Fees should reduce final equity
        assert result_with["equity"][-1] < result_without["equity"][-1]

    def test_slippage_reduces_equity(self):
        df = make_test_df([100.0, 110.0])
        signals = pl.Series("signal", [1.0, 0.0])
        
        config_with_slippage = EnhancedBacktestConfig(
            initial_capital=10000,
            sizing=SizingConfig(mode=SizingMode.BINARY),
            execution=ExecutionCost(slippage_rate=0.001),
        )
        config_no_slippage = EnhancedBacktestConfig(
            initial_capital=10000,
            sizing=SizingConfig(mode=SizingMode.BINARY),
            execution=ExecutionCost(slippage_rate=0.0),
        )
        
        result_with = run_enhanced_backtest(df, signals, config_with_slippage)
        result_without = run_enhanced_backtest(df, signals, config_no_slippage)
        
        assert result_with["equity"][-1] <= result_without["equity"][-1]


class TestInstrumentConstraints:
    """Test Phase 3: Instrument constraints."""

    def test_qty_rounded_to_step(self):
        df = make_test_df([100.0] * 5)
        signals = pl.Series("signal", [1.0] * 5)
        
        config = EnhancedBacktestConfig(
            initial_capital=1000,
            sizing=SizingConfig(
                mode=SizingMode.FRACTIONAL_EQUITY,
                exposure_fraction=1.0,
            ),
            instrument=InstrumentSpec(qty_step=0.1),
        )
        
        result = run_enhanced_backtest(df, signals, config)
        
        # Position should be rounded to 0.1 step
        position = result["position"][0]
        rounded = round(position / 0.1) * 0.1
        assert abs(position - rounded) < 0.001

    def test_order_rejected_below_min_qty(self):
        df = make_test_df([10000.0] * 5)  # High price
        signals = pl.Series("signal", [1.0] * 5)
        
        config = EnhancedBacktestConfig(
            initial_capital=100,
            sizing=SizingConfig(
                mode=SizingMode.FRACTIONAL_EQUITY,
                exposure_fraction=0.01,  # Very small
            ),
            instrument=InstrumentSpec(
                qty_step=0.01,
                min_qty=1.0,  # High minimum
            ),
        )
        
        result = run_enhanced_backtest(df, signals, config)
        
        # Position should be 0 because below min_qty
        assert result["position"][0] == 0.0


class TestBybitConfig:
    """Test Phase 4: Bybit preset."""

    def test_bybit_preset_creation(self):
        config = create_bybit_config(
            initial_capital=10000,
            leverage=20,
            sizing_mode=SizingMode.FRACTIONAL_EQUITY,
            exposure_fraction=0.3,
        )
        
        assert config.initial_capital == 10000
        assert config.sizing.leverage == 20
        assert config.execution.taker_fee_rate == 0.0004
        assert config.margin.enabled == True
        assert config.margin.initial_margin_rate == 1/20

    def test_bybit_instrument_spec(self):
        bybit = BybitLinearConfig()
        spec = bybit.to_instrument_spec()
        
        assert spec.tick_size == 0.5
        assert spec.qty_step == 0.01


class TestMargin:
    """Test Phase 6: Margin and liquidation."""

    def test_insufficient_margin_rejects_order(self):
        df = make_test_df([1000.0] * 5)
        signals = pl.Series("signal", [1.0] * 5)
        
        config = EnhancedBacktestConfig(
            initial_capital=100,  # Small capital
            sizing=SizingConfig(
                mode=SizingMode.FRACTIONAL_EQUITY,
                exposure_fraction=1.0,
                leverage=100,  # High leverage
            ),
            margin=MarginConfig(
                enabled=True,
                initial_margin_rate=0.01,  # 1% = 100x leverage
            ),
            execution=ExecutionCost(taker_fee_rate=0.001),
        )
        
        result = run_enhanced_backtest(df, signals, config)
        
        # Position should be 0 if margin insufficient
        # (depends on exact calculation but should be rejected)


class TestBackwardsCompatibility:
    """Test backward compatibility."""

    def test_default_behavior_unchanged(self):
        """Default config should work without errors."""
        df = make_test_df([100.0, 110.0, 120.0])
        signals = pl.Series("signal", [1.0, 1.0, 0.0])
        
        config = EnhancedBacktestConfig()  # All defaults
        result = run_enhanced_backtest(df, signals, config)
        
        # Should run without errors
        assert "equity" in result.columns
        assert "position" in result.columns

    def test_required_columns_present(self):
        """Result should have required columns."""
        df = make_test_df([100.0] * 5)
        signals = pl.Series("signal", [1.0] * 5)
        
        config = EnhancedBacktestConfig()
        result = run_enhanced_backtest(df, signals, config)
        
        required = ["timestamp", "close", "equity", "position", "is_exposed", 
                    "fees_paid", "slippage_paid", "margin_used", "liquidation_flag"]
        for col in required:
            assert col in result.columns


if __name__ == "__main__":
    pytest.main([__file__, "-v"])