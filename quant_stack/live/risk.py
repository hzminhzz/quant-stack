"""Minimal live risk checks."""

from __future__ import annotations


def clamp_position_size(size: float, *, max_abs_size: float) -> float:
    return max(-max_abs_size, min(max_abs_size, size))


__all__ = ["clamp_position_size"]
