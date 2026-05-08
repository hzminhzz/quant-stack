"""Artifact retrieval helpers for agent bridge."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def fetch_summary(summary_path: str) -> dict[str, Any]:
    """Load a summary JSON artifact from disk."""

    path = Path(summary_path)
    if not path.exists():
        raise FileNotFoundError(f"summary artifact not found: {summary_path}")
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("summary artifact must be a JSON object")
    return payload


__all__ = ["fetch_summary"]
