from __future__ import annotations

from typing import Any, Protocol

import numpy as np
import polars as pl
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from engine.analytics_pro import calculate_prop_metrics
from engine.monte_carlo import run_monte_carlo
from engine.schemas import PropFirmContract
from strategy_families.base import StrategyFamily


class HasDuckDB(Protocol):
    db: Any


class MarketFrameLoadRequest(BaseModel):
    asset: str = Field(..., min_length=1)
    train_years: list[int] = Field(..., min_length=1)
    test_years: list[int] = Field(..., min_length=1)
    data_dir: str = "Data/Binance"


class MarketFrameSet(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    train_close: np.ndarray
    test_close: np.ndarray
    train_df: pl.DataFrame
    test_df: pl.DataFrame


class BacktestPhaseResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    label: str
    metrics: dict[str, Any]
    trades: np.ndarray


class BacktestPhaseRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    close_prices: np.ndarray
    df: pl.DataFrame
    family: StrategyFamily
    params: BaseModel
    label: str
    initial_capital: float = 10000.0


class MonteCarloResult(BaseModel):
    dd_95: float
    dd_50: float


class CROPayload(BaseModel):
    in_sample_metrics: dict[str, Any]
    in_sample_trade_count: int
    out_of_sample_metrics: dict[str, Any]
    out_of_sample_trade_count: int
    monte_carlo_95_dd_absolute_pct: float
    note: str


class CROPayloadRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    in_sample: BacktestPhaseResult
    out_of_sample: BacktestPhaseResult
    monte_carlo: MonteCarloResult


class PhaseValidationRequest(BaseModel):
    label: str
    metrics: dict[str, Any]


class PhaseValidationResult(BaseModel):
    label: str
    rejection_reason: str | None = None


class DeterministicEvaluationRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    family: StrategyFamily
    params: BaseModel
    train_close: np.ndarray
    train_df: pl.DataFrame
    test_close: np.ndarray
    test_df: pl.DataFrame
    mc_seed: int = 42
    mc_num_simulations: int = 1000
    initial_capital: float = 10000.0


class DeterministicEvaluationResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    in_sample: BacktestPhaseResult
    monte_carlo: MonteCarloResult | None = None
    out_of_sample: BacktestPhaseResult | None = None
    deterministic_rejection: str | None = None
    cro_payload: CROPayload | None = None


def load_market_frames(
    deps: HasDuckDB,
    family: StrategyFamily,
    request: MarketFrameLoadRequest,
) -> MarketFrameSet:
    years_all = sorted(set(request.train_years + request.test_years))
    file_patterns = [
        f"'{request.data_dir}/{request.asset}_{family.raw_data_timeframe}_{year}.parquet'"
        for year in years_all
    ]
    union_query = " UNION ALL ".join(
        [
            f"SELECT epoch_ms(timestamp) as timestamp, open, high, low, close, volume FROM read_parquet({pattern})"
            for pattern in file_patterns
        ]
    )
    raw_df = deps.db.sql(f"SELECT * FROM ({union_query}) ORDER BY timestamp ASC").pl()

    train_raw = raw_df.filter(pl.col("timestamp").dt.year().is_in(request.train_years))
    test_raw = raw_df.filter(pl.col("timestamp").dt.year().is_in(request.test_years))

    train_df = family.prepare_market_data(train_raw)
    test_df = family.prepare_market_data(test_raw)

    return MarketFrameSet(
        train_close=train_df["close"].to_numpy(),
        test_close=test_df["close"].to_numpy(),
        train_df=train_df,
        test_df=test_df,
    )


def run_backtest_phase(request: BacktestPhaseRequest) -> BacktestPhaseResult:
    equity, exposed, trades = request.family.simulate(request.close_prices, request.params)
    df_m = request.df.with_columns(
        [
            pl.Series("equity", equity) * request.initial_capital,
            pl.Series("is_exposed", exposed),
        ]
    )
    metrics = calculate_prop_metrics(df_m, initial_capital=request.initial_capital)
    return BacktestPhaseResult(
        label=request.label,
        metrics=metrics,
        trades=np.asarray(trades),
    )


def build_cro_payload(request: CROPayloadRequest) -> CROPayload:
    def safe_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
        return {
            key: float(value) if isinstance(value, (int, float, np.integer, np.floating)) else value
            for key, value in metrics.items()
        }

    return CROPayload(
        in_sample_metrics=safe_metrics(request.in_sample.metrics),
        in_sample_trade_count=int(len(request.in_sample.trades)),
        out_of_sample_metrics=safe_metrics(request.out_of_sample.metrics),
        out_of_sample_trade_count=int(len(request.out_of_sample.trades)),
        monte_carlo_95_dd_absolute_pct=round(abs(request.monte_carlo.dd_95) * 100, 2),
        note="Monte Carlo passes if absolute value < 16%. Reject if 0.0% (ghost alpha).",
    )


def validate_phase_metrics(request: PhaseValidationRequest) -> PhaseValidationResult:
    try:
        _ = PropFirmContract(**request.metrics)
    except ValidationError as exc:
        return PhaseValidationResult(
            label=request.label,
            rejection_reason=(
                f"{request.label} failed deterministic prop-firm validation: {exc.errors()[0]['msg']}"
            ),
        )
    return PhaseValidationResult(label=request.label)


def evaluate_candidate(request: DeterministicEvaluationRequest) -> DeterministicEvaluationResult:
    in_sample = run_backtest_phase(
        BacktestPhaseRequest(
            close_prices=request.train_close,
            df=request.train_df,
            family=request.family,
            params=request.params,
            label="In-Sample",
            initial_capital=request.initial_capital,
        )
    )
    in_sample_validation = validate_phase_metrics(
        PhaseValidationRequest(label=in_sample.label, metrics=in_sample.metrics)
    )
    deterministic_rejection = in_sample_validation.rejection_reason
    if deterministic_rejection is not None:
        return DeterministicEvaluationResult(
            in_sample=in_sample,
            deterministic_rejection=deterministic_rejection,
        )

    mc_95, mc_50 = run_monte_carlo(
        in_sample.trades,
        num_simulations=request.mc_num_simulations,
        seed=request.mc_seed,
    )
    monte_carlo = MonteCarloResult(dd_95=mc_95, dd_50=mc_50)

    out_of_sample = run_backtest_phase(
        BacktestPhaseRequest(
            close_prices=request.test_close,
            df=request.test_df,
            family=request.family,
            params=request.params,
            label="Out-Of-Sample",
            initial_capital=request.initial_capital,
        )
    )
    out_of_sample_validation = validate_phase_metrics(
        PhaseValidationRequest(label=out_of_sample.label, metrics=out_of_sample.metrics)
    )
    deterministic_rejection = out_of_sample_validation.rejection_reason
    if deterministic_rejection is not None:
        return DeterministicEvaluationResult(
            in_sample=in_sample,
            monte_carlo=monte_carlo,
            out_of_sample=out_of_sample,
            deterministic_rejection=deterministic_rejection,
        )

    cro_payload = build_cro_payload(
        CROPayloadRequest(
            in_sample=in_sample,
            out_of_sample=out_of_sample,
            monte_carlo=monte_carlo,
        )
    )
    return DeterministicEvaluationResult(
        in_sample=in_sample,
        monte_carlo=monte_carlo,
        out_of_sample=out_of_sample,
        cro_payload=cro_payload,
    )
