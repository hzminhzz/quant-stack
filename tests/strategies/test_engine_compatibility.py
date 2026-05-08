from __future__ import annotations

import pytest

from quant_stack.strategies import get_strategy
from quant_stack.strategies.specs import EngineCompatibilityError, validate_engine_compatibility


def test_polars_rejects_grid_strategy() -> None:
    strategy = get_strategy("grid")
    with pytest.raises(EngineCompatibilityError):
        validate_engine_compatibility(strategy.spec, "polars")


def test_polars_allows_vectorized_strategy() -> None:
    strategy = get_strategy("rsi_sma")
    validate_engine_compatibility(strategy.spec, "polars")


def test_grid_dca_rejects_rsi_sma() -> None:
    strategy = get_strategy("rsi_sma")
    with pytest.raises(EngineCompatibilityError):
        validate_engine_compatibility(strategy.spec, "grid_dca")
