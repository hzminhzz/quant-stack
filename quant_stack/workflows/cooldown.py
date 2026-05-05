"""In-memory cooldown store for workflow spam prevention."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


class CooldownStore:
    def __init__(self) -> None:
        self._last_triggered: dict[str, datetime] = {}

    def is_on_cooldown(self, key: str, *, cooldown_seconds: int, now: datetime | None = None) -> bool:
        if cooldown_seconds <= 0:
            return False
        current = now or datetime.now(timezone.utc)
        last = self._last_triggered.get(key)
        if last is None:
            return False
        return (current - last) < timedelta(seconds=cooldown_seconds)

    def mark_triggered(self, key: str, *, now: datetime | None = None) -> None:
        self._last_triggered[key] = now or datetime.now(timezone.utc)


__all__ = ["CooldownStore"]
