from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import polars as pl

from quant_stack.api.mcp_adapter import call_tool, handle_jsonrpc, list_tools
from quant_stack.cli.run_api_tools import main as api_tools_main


def _make_dataset(path: Path, n: int = 180) -> None:
    ts = np.datetime64("2026-01-01T00:00:00") + np.arange(0, n * 60 * 1000, 60 * 1000, dtype="timedelta64[ms]")
    close = 100.0 + np.sin(np.linspace(0.0, 8.0, n)) * 2.5 + np.linspace(0.0, 0.5, n)
    frame = pl.DataFrame(
        {
            "timestamp": ts,
            "open": close,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": np.full(n, 1000.0),
        }
    )
    frame.write_parquet(path)


def test_mcp_list_tools_and_strategy_describe() -> None:
    tools = list_tools()
    names = {item["name"] for item in tools}
    assert "strategy.list" in names
    assert "backtest.run" in names

    described = call_tool("strategy.describe", {"strategy_name": "rsi_sma"})
    assert described["name"] == "rsi_sma"


def test_mcp_jsonrpc_error_envelope() -> None:
    reply = handle_jsonrpc({"jsonrpc": "2.0", "id": 11, "method": "tools/call", "params": {"name": "nope"}})
    assert "error" in reply
    assert reply["id"] == 11


def test_cli_api_tools_backtest_run_and_artifact_fetch(tmp_path: Path, capsys) -> None:
    data_path = tmp_path / "sample_cli.parquet"
    _make_dataset(data_path)

    payload = {
        "strategy": "rsi_sma",
        "data_path": str(data_path),
        "params": {"short_sma": 20, "long_sma": 100, "rsi_period": 14, "rsi_threshold": 35.0, "rsi_side": "below"},
        "engine": "polars",
    }
    api_tools_main(["backtest-run", "--payload-json", json.dumps(payload)])
    out = capsys.readouterr().out
    summary = json.loads(out)
    assert summary["status"] == "ok"

    summary_path = summary["artifact_refs"]["metrics_path"]
    api_tools_main(["artifact-fetch-summary", "--summary-path", summary_path])
    fetched_out = capsys.readouterr().out
    fetched = json.loads(fetched_out)
    assert isinstance(fetched, dict)
