"""Registry for new quant_stack strategy modules."""

from __future__ import annotations

from dataclasses import dataclass

from typing import Callable

import polars as pl
from pydantic import BaseModel

from quant_stack.strategies.specs import StrategySpec


@dataclass(frozen=True)
class StrategyModule:
    """Callable strategy package surface."""

    spec: StrategySpec
    params_model: type[BaseModel]
    build_features: Callable[[pl.DataFrame, BaseModel], pl.DataFrame]
    build_signals: Callable[[pl.DataFrame, BaseModel], pl.DataFrame]

    def validate_params(self, params: dict[str, object] | BaseModel) -> BaseModel:
        if isinstance(params, self.params_model):
            return params
        if isinstance(params, BaseModel):
            return self.params_model.model_validate(params.model_dump())
        return self.params_model.model_validate(params)


class StrategyRegistry:
    """In-memory registry for deterministic strategy modules."""

    def __init__(self) -> None:
        self._modules: dict[str, StrategyModule] = {}

    def register(self, module: StrategyModule) -> None:
        key = _normalize_name(module.spec.name)
        if key in self._modules:
            raise ValueError(f"strategy already registered: {module.spec.name}")
        self._modules[key] = module

    def get(self, name: str) -> StrategyModule:
        key = _normalize_name(name)
        try:
            return self._modules[key]
        except KeyError as exc:
            raise KeyError(f"unknown strategy: {name}") from exc

    def available(self) -> list[str]:
        return sorted(self._modules)


def build_default_registry() -> StrategyRegistry:
    from quant_stack.strategies.bb_breakout import module as bb_breakout
    from quant_stack.strategies.forced_flow_band_reclaim import module as forced_flow_band_reclaim
    from quant_stack.strategies.funding_exhaustion_reversal import module as funding_exhaustion_reversal
    from quant_stack.strategies.grid import module as grid
    from quant_stack.strategies.oi_confirmed_trend import module as oi_confirmed_trend
    from quant_stack.strategies.rsi_sma import module as rsi_sma
    from quant_stack.strategies.smart_dca import module as smart_dca

    registry = StrategyRegistry()
    registry.register(rsi_sma.strategy_module())
    registry.register(bb_breakout.strategy_module())
    registry.register(grid.strategy_module())
    registry.register(forced_flow_band_reclaim.strategy_module())
    registry.register(funding_exhaustion_reversal.strategy_module())
    registry.register(oi_confirmed_trend.strategy_module())
    registry.register(smart_dca.strategy_module())
    return registry


def _normalize_name(name: str) -> str:
    return name.strip().lower().replace("-", "_")


_DEFAULT_REGISTRY = build_default_registry()


def available_strategies() -> list[str]:
    return _DEFAULT_REGISTRY.available()


def get_strategy(name: str) -> StrategyModule:
    return _DEFAULT_REGISTRY.get(name)


__all__ = ["StrategyModule", "StrategyRegistry", "available_strategies", "get_strategy"]
