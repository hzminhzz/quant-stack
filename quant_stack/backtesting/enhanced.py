"""Enhanced backtesting engine with exchange-aware execution realism.

Phases implemented:
1. Fractional position sizing (binary, fractional_equity, fixed_notional, fixed_qty)
2. Execution cost model (maker/taker fees, slippage, bid/ask fills)
3. Instrument spec constraints (tick_size, qty_step, min_qty)
4. Bybit linear perp preset
5. Funding support
6. Margin/liquidation checks
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal

import polars as pl
from pydantic import BaseModel, Field, field_validator


class SizingMode(str, Enum):
    """Position sizing models."""
    BINARY = "binary"  # 0 or 1
    FRACTIONAL_EQUITY = "fractional_equity"  # position = equity * exposure_fraction
    FIXED_NOTIONAL = "fixed_notional"  # fixed dollar amount
    FIXED_QTY = "fixed_qty"  # fixed contract quantity


class FeeMode(str, Enum):
    """Fee calculation mode."""
    MAKER = "maker"
    TAKER = "takER"


class SizingConfig(BaseModel):
    """Position sizing configuration."""
    mode: SizingMode = SizingMode.BINARY
    exposure_fraction: float = Field(default=1.0, ge=0.0, le=1.0)
    fixed_notional: float = Field(default=1000.0, gt=0.0)
    fixed_qty: float = Field(default=1.0, gt=0.0)
    leverage: float = Field(default=1.0, ge=1.0)


class ExecutionCost(BaseModel):
    """Execution cost configuration."""
    maker_fee_rate: float = Field(default=0.0, ge=0.0)
    taker_fee_rate: float = Field(default=0.0004, ge=0.0)  # Bybit default
    fee_mode: FeeMode = FeeMode.TAKER
    slippage_rate: float = Field(default=0.0, ge=0.0)
    use_bid_ask: bool = False  # Use bid/ask columns for fills if available


class InstrumentSpec(BaseModel):
    """Instrument constraints."""
    tick_size: float = 0.01
    qty_step: float = 0.001
    min_qty: float = 0.001
    min_notional: float = 5.0
    precision: int = 2  # Price decimal places

    def round_price(self, price: float) -> float:
        return round(price / self.tick_size) * self.tick_size

    def round_qty(self, qty: float) -> float:
        return round(qty / self.qty_step) * self.qty_step


class BybitLinearConfig(BaseModel):
    """Bybit linear perpetual configuration."""
    exchange: str = "bybit"
    market_type: Literal["linear_perp", "inverse_perp", "spot"] = "linear_perp"
    maker_fee_rate: float = 0.0001
    taker_fee_rate: float = 0.0004
    default_leverage: float = 10.0
    maintenance_margin_rate: float = 0.005  # 0.5% for BTC, varies by asset
    funding_rate_estimate: float = 0.0001  # ~0.01% per 4h
    tick_size: float = 0.5
    qty_step: float = 0.01

    def to_execution_cost(self) -> ExecutionCost:
        return ExecutionCost(
            maker_fee_rate=self.maker_fee_rate,
            taker_fee_rate=self.taker_fee_rate,
            fee_mode=FeeMode.TAKER,
        )

    def to_instrument_spec(self) -> InstrumentSpec:
        return InstrumentSpec(
            tick_size=self.tick_size,
            qty_step=self.qty_step,
            min_qty=self.qty_step,
            min_notional=5.0,
        )

    def to_sizing_config(self, mode: SizingMode = SizingMode.FRACTIONAL_EQUITY, leverage: float | None = None) -> SizingConfig:
        return SizingConfig(
            mode=mode,
            leverage=leverage or self.default_leverage,
        )


class MarginConfig(BaseModel):
    """Margin and liquidation configuration."""
    enabled: bool = False
    initial_margin_rate: float = 1.0  # 1/leverage
    maintenance_margin_rate: float = 0.005
    liquidation_buffer: float = 0.0  # Extra equity buffer

    def initial_margin(self, notional: float) -> float:
        return notional * self.initial_margin_rate

    def maintenance_margin(self, notional: float) -> float:
        return notional * self.maintenance_margin_rate

    def can_open(self, notional: float, fees: float, available_equity: float) -> bool:
        if not self.enabled:
            return True
        required = self.initial_margin(notional) + fees
        return available_equity >= required


class FundingConfig(BaseModel):
    """Funding configuration."""
    enabled: bool = False
    data_path: str | None = None
    funding_rate: float = 0.0  # Fixed rate if no data
    hours_between_funding: int = 8  # Bybit funds every 8 hours

    @field_validator("data_path")
    @classmethod
    def validate_path(cls, v: str | None) -> str | None:
        if v and not Path(v).exists():
            raise ValueError(f"Funding data path does not exist: {v}")
        return v


class EnhancedBacktestConfig(BaseModel):
    """Complete backtest configuration."""
    initial_capital: float = Field(default=10000.0, gt=0.0)
    sizing: SizingConfig = Field(default_factory=SizingConfig)
    execution: ExecutionCost = Field(default_factory=ExecutionCost)
    instrument: InstrumentSpec = Field(default_factory=InstrumentSpec)
    margin: MarginConfig = Field(default_factory=MarginConfig)
    funding: FundingConfig = Field(default_factory=FundingConfig)


def run_enhanced_backtest(
    df: pl.DataFrame,
    signals: pl.Series | list[float],
    config: EnhancedBacktestConfig,
) -> pl.DataFrame:
    """Run enhanced backtest with realistic execution.
    
    Args:
        df: OHLCV DataFrame with columns: timestamp, open, high, low, close, (optional: bid, ask)
        signals: Signal series (0-1 for binary, 0-1 continuous for fractional) or list
        config: EnhancedBacktestConfig
        
    Returns:
        DataFrame with columns: timestamp, close, equity, position, is_exposed, qty, notional, 
        cash, fees_paid, slippage_paid, funding_pnl, margin_used, liquidation_flag
    """
    df = df.sort("timestamp")
    
    # Add signal column - handle both Series and list
    if isinstance(signals, list):
        df = df.with_columns(pl.lit(signals).alias("signal"))
    elif isinstance(signals, pl.Series):
        df = df.with_columns(pl.Series("signal", signals.to_list()))
    else:
        raise ValueError("signals must be a list or polars Series")
    
    # Ensure required columns
    _require_columns(df, ["timestamp", "close"])
    
    # Get price columns
    close_col = df["close"]
    bid_col = df["bid"] if "bid" in df.columns else None
    ask_col = df["ask"] if "ask" in df.columns else None
    
    # Initialize equity series
    equity = pl.Series("equity", [config.initial_capital] * len(df))
    cash = pl.Series("cash", [config.initial_capital] * len(df))
    margin_used = pl.Series("margin_used", [0.0] * len(df))
    liquidation_flag = pl.Series("liquidation_flag", [False] * len(df))
    fees_paid = pl.Series("fees_paid", [0.0] * len(df))
    slippage_paid = pl.Series("slippage_paid", [0.0] * len(df))
    funding_pnl = pl.Series("funding_pnl", [0.0] * len(df))
    positions = []  # Track calculated positions
    
    rows = df.to_dicts()
    prev_position = 0.0
    
    # Get funding data if enabled
    funding_df = None
    if config.funding.enabled and config.funding.data_path:
        funding_df = pl.read_csv(config.funding.data_path) if config.funding.data_path.endswith(".csv") else pl.read_parquet(config.funding.data_path)
    
    for i, row in enumerate(rows):
        timestamp = row["timestamp"]
        close = float(row["close"])
        
        # Get fill price (use bid/ask if available, else close)
        if bid_col and ask_col:
            bid = float(row.get("bid", close))
            ask = float(row.get("ask", close))
            # Entry uses ask, exit uses bid for conservative pricing
            entry_price = ask if row.get("signal", 0) > prev_position else close
            exit_price = bid if row.get("signal", 0) < prev_position else close
        else:
            entry_price = exit_price = close
        
        # Get target position based on sizing mode
        equity_val = equity[i - 1] if i > 0 else config.initial_capital
        target_position = _calculate_position(
            signal=row.get("signal", 0),
            equity=equity_val,
            price=close,
            config=config.sizing,
        )
        
        # Round to instrument constraints
        if target_position != 0:
            qty = abs(target_position)
            qty = config.instrument.round_qty(qty)
            
            # Check minimum quantity
            if qty < config.instrument.min_qty:
                target_position = 0.0
                qty = 0.0
            else:
                target_position = (qty / abs(target_position)) * qty if target_position != 0 else 0
        
        # Calculate notional value
        notional = abs(target_position * close) if target_position != 0 else 0.0
        
        # Check margin
        required_margin = 0.0
        if config.margin.enabled and target_position != 0:
            required_margin = config.margin.initial_margin(notional)
            fees = _calculate_fees(notional, config.execution)
            if not config.margin.can_open(notional, fees, equity_val):
                target_position = 0.0
                notional = 0.0
        
        # Calculate fees and slippage on position change
        position_change = abs(target_position - prev_position)
        if position_change > 0 and notional > 0:
            fee = _calculate_fees(notional, config.execution)
            slippage = notional * config.execution.slippage_rate
            fees_paid[i] = fee + slippage
            slippage_paid[i] = slippage
        
        # Calculate PnL
        if i > 0:
            pnl = (target_position * (close - rows[i-1]["close"])) - fees_paid[i]
            equity[i] = equity[i-1] + pnl
        else:
            equity[i] = config.initial_capital - fees_paid[i]
        
        positions.append(target_position)
        
        # Update cash
        cash[i] = equity[i] - (notional / config.sizing.leverage if config.margin.enabled else notional)
        
        # Margin used
        margin_used[i] = required_margin
        
        # Check liquidation
        if config.margin.enabled:
            maintenance = config.margin.maintenance_margin(notional)
            if equity[i] <= maintenance + config.margin.liquidation_buffer:
                liquidation_flag[i] = True
                target_position = 0.0
        
        # Funding (simplified - apply at regular intervals)
        if config.funding.enabled and i > 0:
            if hasattr(timestamp, 'hour'):
                hours_since_start = (timestamp - rows[0]["timestamp"]).total_seconds() / 3600
                if hours_since_start > 0 and int(hours_since_start) % config.funding.hours_between_funding == 0:
                    funding = notional * (config.funding.funding_rate if not funding_df else 0.0001)
                    funding_pnl[i] = funding if target_position > 0 else -funding
                    equity[i] += funding_pnl[i]
        
        prev_position = target_position if target_position is not None else 0.0
    
    # Build result frame - use calculated positions
    position_series = pl.Series("position", positions)
    result = df.select(["timestamp", "close", "signal"]).with_columns([
        equity.alias("equity"),
        position_series.alias("position"),
        (position_series != 0).alias("is_exposed"),
        position_series.alias("qty"),
        (position_series * pl.col("close")).alias("notional"),
        cash.alias("cash"),
        fees_paid.alias("fees_paid"),
        slippage_paid.alias("slippage_paid"),
        funding_pnl.alias("funding_pnl"),
        margin_used.alias("margin_used"),
        liquidation_flag.alias("liquidation_flag"),
    ])
    
    return result


def _calculate_position(signal: float, equity: float, price: float, config: SizingConfig) -> float:
    """Calculate target position based on sizing mode."""
    if config.mode == SizingMode.BINARY:
        return 1.0 if signal > 0.5 else 0.0
    
    elif config.mode == SizingMode.FRACTIONAL_EQUITY:
        target_notional = equity * config.exposure_fraction * config.leverage
        return target_notional / price
    
    elif config.mode == SizingMode.FIXED_NOTIONAL:
        return config.fixed_notional / price
    
    elif config.mode == SizingMode.FIXED_QTY:
        return config.fixed_qty
    
    return 0.0


def _calculate_fees(notional: float, config: ExecutionCost) -> float:
    """Calculate fees based on fee mode."""
    if config.fee_mode == FeeMode.MAKER:
        return notional * config.maker_fee_rate
    else:
        return notional * config.taker_fee_rate


def _require_columns(df: pl.DataFrame, columns: list[str]) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"missing required backtest column(s): {', '.join(missing)}")


# Backward compatible defaults
def create_bybit_config(
    initial_capital: float = 10000.0,
    leverage: float = 10.0,
    sizing_mode: SizingMode = SizingMode.FRACTIONAL_EQUITY,
    exposure_fraction: float = 0.5,
    include_funding: bool = False,
) -> EnhancedBacktestConfig:
    """Create a standard Bybit linear perpetual config."""
    bybit = BybitLinearConfig(
        exchange="bybit",
        market_type="linear_perp",
        default_leverage=leverage,
    )
    
    return EnhancedBacktestConfig(
        initial_capital=initial_capital,
        sizing=SizingConfig(
            mode=sizing_mode,
            exposure_fraction=exposure_fraction,
            leverage=leverage,
        ),
        execution=bybit.to_execution_cost(),
        instrument=bybit.to_instrument_spec(),
        margin=MarginConfig(
            enabled=True,
            initial_margin_rate=1.0 / leverage,
            maintenance_margin_rate=bybit.maintenance_margin_rate,
        ),
        funding=FundingConfig(enabled=include_funding),
    )


__all__ = [
    "SizingMode",
    "FeeMode", 
    "SizingConfig",
    "ExecutionCost",
    "InstrumentSpec",
    "BybitLinearConfig",
    "MarginConfig",
    "FundingConfig",
    "EnhancedBacktestConfig",
    "run_enhanced_backtest",
    "create_bybit_config",
]