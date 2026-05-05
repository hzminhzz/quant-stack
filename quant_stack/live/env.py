"""Live environment checks."""

from __future__ import annotations

import os


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"required environment variable missing: {name}")
    return value


__all__ = ["require_env"]
