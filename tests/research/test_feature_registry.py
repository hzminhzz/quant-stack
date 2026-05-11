from __future__ import annotations

import pytest

from quant_stack.research.feature_registry import get_research_feature_registry, research_feature


def test_research_feature_registers_metadata() -> None:
    registry = get_research_feature_registry()
    before = {m.name for m in registry.list()}

    @research_feature(name="unit_test_feature_registry", category="ml", lookback=3)
    def _feature() -> int:
        return 1

    metadata = registry.get("unit_test_feature_registry")
    assert metadata.func is _feature
    assert metadata.category == "ml"
    assert metadata.lookback == 3

    after = {m.name for m in registry.list()}
    assert "unit_test_feature_registry" in after
    assert before.issubset(after)


def test_research_feature_rejects_duplicate_name() -> None:
    @research_feature(name="unit_test_duplicate_registry")
    def _feature_a() -> int:
        return 1

    with pytest.raises(ValueError, match="already registered"):
        @research_feature(name="unit_test_duplicate_registry")
        def _feature_b() -> int:
            return 2
