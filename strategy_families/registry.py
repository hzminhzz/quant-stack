from __future__ import annotations

from strategy_families.base import StrategyFamily
from strategy_families.bb_family import BBStrategyFamily
from strategy_families.rsi_family import RSIStrategyFamily
from strategy_families.grid_family import GridFamily


_FAMILIES: dict[str, StrategyFamily] = {
    "bb": BBStrategyFamily(),
    "rsi": RSIStrategyFamily(),
    "volatility_grid": GridFamily(),
}


def get_strategy_family(name: str) -> StrategyFamily:
    normalized = name.strip().lower()
    if normalized not in _FAMILIES:
        raise ValueError(f"Unknown strategy family: {name}")
    return _FAMILIES[normalized]


def available_strategy_families() -> list[str]:
    return sorted(_FAMILIES.keys())
