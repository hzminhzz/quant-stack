"""Bollinger Band live state."""

from __future__ import annotations

from dataclasses import dataclass

from quant_stack.indicators.live.rolling_std_state import RollingStdState


@dataclass
class BollingerBandState:
    window: int
    num_std: float = 2.0

    def __post_init__(self) -> None:
        self._rolling = RollingStdState(self.window)

    def step(self, close: float) -> tuple[float, float, float]:
        middle, std = self._rolling.step(close)
        return middle, middle + self.num_std * std, middle - self.num_std * std


__all__ = ["BollingerBandState"]
