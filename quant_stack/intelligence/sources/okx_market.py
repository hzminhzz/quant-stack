"""Shared read-only OKX public market fetch helpers."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


OKX_PUBLIC_BASE = "https://www.okx.com"


def fetch_okx_public(path: str, params: dict[str, Any] | None = None, *, timeout: int = 10) -> dict[str, Any]:
    query = f"?{urlencode(params)}" if params else ""
    url = f"{OKX_PUBLIC_BASE}{path}{query}"
    request = Request(url, method="GET", headers={"User-Agent": "quant-stack-intelligence/1.0"})
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload


__all__ = ["OKX_PUBLIC_BASE", "fetch_okx_public"]
