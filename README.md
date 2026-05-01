# Quant Factory

## Local paper-search MCP access from Python

This machine can call the installed `paper-search-mcp` server directly from Python over MCP stdio.

### Files

- `paper_search_client.py` — thin async Python client for the local MCP server
- `paper_search_demo.py` — runnable example CLI using that client
- `paper_context.py` — shared query/normalization/formatting helpers used by discovery and research

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

`research.py` now uses the local paper-search MCP integration as an early step in the workflow.
It loads the latest LanceDB signal, searches for supporting papers, feeds that literature context
into the DSPy prompt, and then generates the Polars backtest code.

Both `research.py` and `discovery.py` now share the same `paper_context.py` normalization,
formatting, summary printing, and sync/async fetch helpers.

### Example

```bash
uv run python research.py --paper-sources crossref,openalex,semantic,ssrn,arxiv --paper-max-results 2
```

Useful flags:

- `--skip-paper-search` to bypass the MCP lookup
- `--paper-year 2024-2026` to restrict literature search
- `--lancedb-path` / `--signal-table` / `--data-path` to point at non-default local data

## Discovery flow with paper context

`discovery.py` can now enrich signal extraction with supporting paper context before writing the
structured signal to LanceDB. The stored LanceDB schema is unchanged, so `research.py` continues
to consume the same `signals` table shape.

### Example

```bash
uv run python discovery.py --paper-sources crossref,openalex,semantic,ssrn,arxiv --paper-max-results 2
```

Useful flags:

- `--skip-paper-search` to keep the old extraction path
- `--source-path some_other_paper.html` to crawl a different local paper file
- `--paper-year 2024-2026` to narrow retrieval
