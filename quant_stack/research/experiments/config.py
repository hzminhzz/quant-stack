"""Config helpers for Phase 18F strategy experiments."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_params_json(path: str | None) -> dict[str, Any]:
    if path is None:
        return {}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("params JSON must decode to an object")
    return payload


def build_mode_params(default_params: dict[str, Any], overrides: dict[str, Any], *, context_mode: bool) -> dict[str, Any]:
    params = {**default_params, **overrides}
    if "use_context_filters" in params:
        params["use_context_filters"] = bool(context_mode)
    return params


__all__ = ["build_mode_params", "load_params_json"]
