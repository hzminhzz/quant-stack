# Quant Factory

## Canonical Entry Point

All new work should use `quant_stack/` as the canonical package:

```bash
uv run python -m quant_stack.cli.main --help
```

Available commands: `backtest`, `experiment`, `build-bybit-dataset`, `research`, `walk-forward`, `acceptance`, `phase19`

## Local paper-search MCP access from Python

This machine can call the installed `paper-search-mcp` server directly from Python over MCP stdio.

### Files

- `paper_search_client.py` — thin async Python client for the local MCP server
- `paper_search_demo.py` — runnable example CLI using that client
- `paper_context.py` — shared query/normalization/formatting helpers

### Run the demo

```bash
uv run python paper_search_demo.py "statistical arbitrage" --sources crossref,openalex,semantic,ssrn,arxiv --max-results 2
```

### Use from Python code

```python
import asyncio

from paper_search_client import PaperSearchMCPClient


async def main() -> None:
    async with PaperSearchMCPClient() as client:
        result = await client.search_papers(
            query="pairs trading",
            max_results_per_source=2,
            sources="crossref,openalex,semantic,ssrn,arxiv",
        )
        print(result)


asyncio.run(main())
```

If `paper-search-mcp` is not on your `PATH`, set `PAPER_SEARCH_MCP_COMMAND` to the executable path.

## Research flow with paper context

`quant_stack/cli/research` uses the local paper-search MCP integration. It loads the latest LanceDB signal, searches for supporting papers, and generates Polars backtest code.

### Example

```bash
uv run python -m quant_stack.cli.main research --paper-sources crossref,openalex,semantic,ssrn,arxiv --paper-max-results 2
```

Useful flags:

- `--skip-paper-search` to bypass the MCP lookup
- `--paper-year 2024-2026` to restrict literature search
- `--lancedb-path` / `--signal-table` / `--data-path` to point at non-default local data