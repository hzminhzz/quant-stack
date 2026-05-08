# Quant Stack API Tools Integration

This document describes the Phase 3 bridge endpoints and how to use them from:

1. Python tool calls (`quant_stack.api.tools`)
2. CLI wrappers (`quant_stack.cli.main api-tools ...`)
3. MCP-style adapter (`quant_stack.api.mcp_adapter`)

## Tool Endpoints

- `strategy.list`
- `strategy.describe`
- `backtest.run`
- `backtest.batch`
- `artifact.fetch_summary`

## 1) Python usage

```python
from quant_stack.api.tools import strategy_list, strategy_describe, backtest_run

print(strategy_list())
print(strategy_describe("rsi_sma"))

payload = {
    "strategy": "rsi_sma",
    "data_path": "data/btc_1m.parquet",
    "params": {
        "short_sma": 20,
        "long_sma": 100,
        "rsi_period": 14,
        "rsi_threshold": 35.0,
        "rsi_side": "below"
    },
    "engine": "polars",
    "output_mode": "summary"
}

summary = backtest_run(payload)
print(summary["metrics"])
```

## 2) CLI wrappers

### Strategy list

```bash
uv run python -m quant_stack.cli.main api-tools strategy-list
```

### Strategy describe

```bash
uv run python -m quant_stack.cli.main api-tools strategy-describe --strategy rsi_sma
```

### Single backtest run

```bash
uv run python -m quant_stack.cli.main api-tools backtest-run \
  --payload-json '{
    "strategy":"rsi_sma",
    "data_path":"data/btc_1m.parquet",
    "params":{
      "short_sma":20,
      "long_sma":100,
      "rsi_period":14,
      "rsi_threshold":35.0,
      "rsi_side":"below"
    },
    "engine":"polars"
  }'
```

### Batch backtest run

```bash
uv run python -m quant_stack.cli.main api-tools backtest-batch \
  --payload-json '{
    "strategy":"rsi_sma",
    "data_path":"data/btc_1m.parquet",
    "param_matrix":[
      {"short_sma":20,"long_sma":100,"rsi_period":10,"rsi_threshold":35.0,"rsi_side":"below"},
      {"short_sma":25,"long_sma":120,"rsi_period":14,"rsi_threshold":40.0,"rsi_side":"below"}
    ],
    "top_n":1
  }'
```

### Artifact summary fetch

```bash
uv run python -m quant_stack.cli.main api-tools artifact-fetch-summary \
  --summary-path artifacts/api/<run_id>/summary.json
```

## 3) MCP-style adapter

### List tools

```python
from quant_stack.api.mcp_adapter import handle_jsonrpc

request = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list",
    "params": {}
}
print(handle_jsonrpc(request))
```

### Call a tool

```python
request = {
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
        "name": "strategy.describe",
        "arguments": {"strategy_name": "rsi_sma"}
    }
}
print(handle_jsonrpc(request))
```

## Notes

- Output is **summary-first** (agent-safe). No full DataFrame payloads at the tool boundary.
- `backtest.run` and `backtest.batch` currently validate against `polars` execution path in this phase.
- Artifacts are persisted under `artifacts/api/<run_id>/`.
