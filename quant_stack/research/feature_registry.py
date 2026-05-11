"""Research-layer feature registry inspired by ml4t/engineer patterns.

This registry is intentionally scoped to research workflows and metadata discovery.
It does not execute features inside deterministic backtesting engines.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ResearchFeatureMetadata:
    name: str
    func: Callable[..., Any]
    category: str = "research"
    description: str = ""
    lookback: int = 0
    tags: tuple[str, ...] = field(default_factory=tuple)


class ResearchFeatureRegistry:
    def __init__(self) -> None:
        self._features: dict[str, ResearchFeatureMetadata] = {}

    def register(self, metadata: ResearchFeatureMetadata) -> None:
        if metadata.name in self._features:
            raise ValueError(f"feature '{metadata.name}' is already registered")
        self._features[metadata.name] = metadata

    def get(self, name: str) -> ResearchFeatureMetadata:
        if name not in self._features:
            raise KeyError(f"feature '{name}' is not registered")
        return self._features[name]

    def list(self) -> list[ResearchFeatureMetadata]:
        return [self._features[key] for key in sorted(self._features)]


_global_registry = ResearchFeatureRegistry()


def get_research_feature_registry() -> ResearchFeatureRegistry:
    return _global_registry


def research_feature(
    *,
    name: str,
    category: str = "research",
    description: str = "",
    lookback: int = 0,
    tags: tuple[str, ...] = (),
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that registers metadata and returns the original function."""

    def _decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        metadata = ResearchFeatureMetadata(
            name=name,
            func=func,
            category=category,
            description=description,
            lookback=lookback,
            tags=tags,
        )
        get_research_feature_registry().register(metadata)
        return func

    return _decorator


__all__ = [
    "ResearchFeatureMetadata",
    "ResearchFeatureRegistry",
    "get_research_feature_registry",
    "research_feature",
]
