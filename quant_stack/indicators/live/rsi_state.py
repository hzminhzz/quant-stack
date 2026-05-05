"""Wilder RSI live state."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import numpy as np


@dataclass
class RSIState:
    period: int
    previous_close: float | None = None
    avg_gain: float = 0.0
    avg_loss: float = 0.0
    gains: deque[float] = field(default_factory=deque)
    losses: deque[float] = field(default_factory=deque)
    ready: bool = False

    def step(self, close: float) -> float:
        close = float(close)
        if self.previous_close is None:
            self.previous_close = close
            return np.nan
        diff = close - self.previous_close
        self.previous_close = close
        gain = max(diff, 0.0)
        loss = max(-diff, 0.0)
        if not self.ready:
            self.gains.append(gain)
            self.losses.append(loss)
            if len(self.gains) < self.period:
                return np.nan
            self.avg_gain = sum(self.gains) / self.period
            self.avg_loss = sum(self.losses) / self.period
            self.ready = True
        else:
            self.avg_gain = ((self.avg_gain * (self.period - 1)) + gain) / self.period
            self.avg_loss = ((self.avg_loss * (self.period - 1)) + loss) / self.period
        if self.avg_loss == 0.0:
            return 100.0
        rs = self.avg_gain / self.avg_loss
        return 100.0 - (100.0 / (1.0 + rs))


__all__ = ["RSIState"]
