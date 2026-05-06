"""Forced-flow proxy band reclaim strategy module factory."""

from __future__ import annotations

from typing import TYPE_CHECKING

import polars as pl
from pydantic import BaseModel

from quant_stack.strategies.forced_flow_band_reclaim.params import ForcedFlowBandReclaimParams
from quant_stack.strategies.forced_flow_band_reclaim.signals import build_features as _build_features_impl
from quant_stack.strategies.forced_flow_band_reclaim.signals import build_signals as _build_signals_impl
from quant_stack.strategies.forced_flow_band_reclaim.spec import SPEC

if TYPE_CHECKING:
    from quant_stack.strategies.registry import StrategyModule


def _coerce_params(params: BaseModel) -> ForcedFlowBandReclaimParams:
    if isinstance(params, ForcedFlowBandReclaimParams):
        return params
    return ForcedFlowBandReclaimParams.model_validate(params.model_dump())


def build_features(df: pl.DataFrame, params: BaseModel) -> pl.DataFrame:
    return _build_features_impl(df, _coerce_params(params))


def build_signals(df: pl.DataFrame, params: BaseModel) -> pl.DataFrame:
    return _build_signals_impl(df, _coerce_params(params))


def strategy_module() -> StrategyModule:
    from quant_stack.strategies.registry import StrategyModule

    return StrategyModule(SPEC, ForcedFlowBandReclaimParams, build_features, build_signals)


__all__ = ["strategy_module"]
