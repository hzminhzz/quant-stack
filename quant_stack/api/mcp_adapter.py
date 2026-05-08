"""MCP-style adapter around quant_stack API tools."""

from __future__ import annotations

from typing import Any

from quant_stack.api.tools import TOOLS


def list_tools() -> list[dict[str, str]]:
    """Return MCP-style tool descriptors."""

    descriptions = {
        "strategy.list": "List strategy names",
        "strategy.describe": "Describe one strategy and params schema",
        "backtest.run": "Run one deterministic backtest from payload",
        "backtest.batch": "Run parameter batch and return top summaries",
        "artifact.fetch_summary": "Load summary artifact JSON from disk",
    }
    return [
        {"name": name, "description": descriptions.get(name, "")}
        for name in sorted(TOOLS.keys())
    ]


def call_tool(name: str, arguments: dict[str, Any] | None = None) -> Any:
    """Invoke one tool by name with named arguments payload."""

    if name not in TOOLS:
        raise KeyError(f"unknown tool: {name}")
    args = arguments or {}
    fn = TOOLS[name]

    if name == "strategy.list":
        return fn()
    if name == "strategy.describe":
        return fn(args["strategy_name"])
    if name in {"backtest.run", "backtest.batch"}:
        return fn(args["payload"])
    if name == "artifact.fetch_summary":
        return fn(args["summary_path"])
    raise KeyError(f"unhandled tool route: {name}")


def handle_jsonrpc(request: dict[str, Any]) -> dict[str, Any]:
    """Handle minimal JSON-RPC-like MCP request envelope."""

    method = request.get("method")
    req_id = request.get("id")
    params = request.get("params") or {}

    try:
        if method == "tools/list":
            result = list_tools()
        elif method == "tools/call":
            result = call_tool(params["name"], params.get("arguments"))
        else:
            raise ValueError(f"unsupported method: {method}")
        return {"jsonrpc": "2.0", "id": req_id, "result": result}
    except Exception as exc:  # explicit bridge error envelope
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32000,
                "message": str(exc),
            },
        }


__all__ = ["call_tool", "handle_jsonrpc", "list_tools"]
