"""O(1) EMA live state."""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from numba import njit


@njit
def ema_update(previous: float, value: float, alpha: float, initialized: bool) -> float:
    return value if not initialized else (alpha * value) + ((1.0 - alpha) * previous)


@dataclass
class EMAState:
    span: int
    value: float = np.nan
    count: int = 0

    def step(self, value: float) -> float:
        alpha = 2.0 / (self.span + 1.0)
        self.value = float(ema_update(self.value, float(value), alpha, self.count > 0))
        self.count += 1
        return self.value if self.count >= self.span else np.nan


__all__ = ["EMAState", "ema_update"]
