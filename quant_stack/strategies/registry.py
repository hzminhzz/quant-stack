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
    from quant_stack.strategies.grid import module as grid
    from quant_stack.strategies.rsi_sma import module as rsi_sma

    registry = StrategyRegistry()
    registry.register(rsi_sma.strategy_module())
    registry.register(bb_breakout.strategy_module())
    registry.register(grid.strategy_module())
    return registry


def _normalize_name(name: str) -> str:
    return name.strip().lower().replace("-", "_")


_DEFAULT_REGISTRY = build_default_registry()


def available_strategies() -> list[str]:
    return _DEFAULT_REGISTRY.available()


def get_strategy(name: str) -> StrategyModule:
    return _DEFAULT_REGISTRY.get(name)


__all__ = ["StrategyModule", "StrategyRegistry", "available_strategies", "get_strategy"]
