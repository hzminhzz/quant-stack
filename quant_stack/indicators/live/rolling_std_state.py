"""Rolling mean/std live state using fixed-size NumPy buffers."""

from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np


@dataclass
class RollingStdState:
    window: int
    buffer: np.ndarray = field(init=False)
    index: int = 0
    count: int = 0
    total: float = 0.0
    total_sq: float = 0.0

    def __post_init__(self) -> None:
        self.buffer = np.zeros(self.window, dtype=np.float64)

    def step(self, value: float) -> tuple[float, float]:
        value = float(value)
        if self.count >= self.window:
            old = float(self.buffer[self.index])
            self.total -= old
            self.total_sq -= old * old
        else:
            self.count += 1
        self.buffer[self.index] = value
        self.total += value
        self.total_sq += value * value
        self.index = (self.index + 1) % self.window
        if self.count < self.window:
            return np.nan, np.nan
        mean = self.total / self.window
        variance = max((self.total_sq / self.window) - (mean * mean), 0.0)
        return mean, float(np.sqrt(variance))


__all__ = ["RollingStdState"]
