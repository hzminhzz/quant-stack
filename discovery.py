from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any

import lancedb
from crawl4ai import AsyncWebCrawler
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from paper_context import (
    DEFAULT_PAPER_SOURCES,
    build_paper_query_from_source_text,
    fetch_paper_context_async,
    print_paper_summary,
)
from pipeline_artifacts import DEFAULT_SIGNAL_ARTIFACT_PATH, SignalArtifact, save_signal_artifact
from strategy_families import available_strategy_families, get_strategy_family


DEFAULT_SOURCE_PATH = "https://arxiv.org/html/2602.10785"
DEFAULT_LANCEDB_PATH = "./data/lancedb"
DEFAULT_SIGNAL_TABLE = "signals"


provider = OpenAIProvider(
    base_url="http://127.0.0.1:8000/v1",
    api_key="anything",
)

research_model = OpenAIChatModel(
    "gpt-5.4",
    provider=provider,
)

@dataclass
class DiscoveryConfig:
    family: str
    source_path: str
    lancedb_path: str
    signal_table: str
    artifact_path: str
    paper_sources: str
    paper_year: str | None
    paper_max_results: int
    skip_paper_search: bool


def parse_args() -> DiscoveryConfig:
    parser = argparse.ArgumentParser(description="Phase 1/2 discovery flow with optional local paper-search MCP support")
    parser.add_argument("--family", choices=available_strategy_families(), default="rsi")
    parser.add_argument("--source-path", default=DEFAULT_SOURCE_PATH)
    parser.add_argument("--lancedb-path", default=DEFAULT_LANCEDB_PATH)
    parser.add_argument("--signal-table", default=DEFAULT_SIGNAL_TABLE)
    parser.add_argument("--artifact-path", default=str(DEFAULT_SIGNAL_ARTIFACT_PATH))
    parser.add_argument("--paper-sources", default=DEFAULT_PAPER_SOURCES)
    parser.add_argument("--paper-year", default=None)
    parser.add_argument("--paper-max-results", type=int, default=2)
    parser.add_argument("--skip-paper-search", action="store_true")
    args = parser.parse_args()

    return DiscoveryConfig(
        family=args.family,
        source_path=args.source_path,
        lancedb_path=args.lancedb_path,
        signal_table=args.signal_table,
        artifact_path=args.artifact_path,
        paper_sources=args.paper_sources,
        paper_year=args.paper_year,
        paper_max_results=args.paper_max_results,
        skip_paper_search=args.skip_paper_search,
    )


def build_source_file_url(source_path: str) -> str:
    return f"file://{os.path.abspath(source_path)}"


async def crawl_source_text(source_path: str) -> str:
    if source_path.startswith("http://") or source_path.startswith("https://"):
        url = source_path
    else:
        url = build_source_file_url(source_path)
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url)
    return result.markdown


async def fetch_paper_context(config: DiscoveryConfig, raw_markdown: str) -> tuple[str, dict[str, Any] | None]:
    query = build_paper_query_from_source_text(raw_markdown, config.source_path)
    return await fetch_paper_context_async(
        query=query,
        sources=config.paper_sources,
        year=config.paper_year,
        max_results_per_source=config.paper_max_results,
        skip_paper_search=config.skip_paper_search,
    )


def extract_signal_from_result(extraction_result: Any) -> BaseModel:
    try:
        return extraction_result.data
    except AttributeError:
        signal = getattr(extraction_result, "output", getattr(extraction_result, "data", None))
        if signal is None:
            raise RuntimeError("Signal extraction did not return structured output.")
        return signal


async def run_signal_extraction(config: DiscoveryConfig, raw_markdown: str, paper_context: str) -> BaseModel:
    family = get_strategy_family(config.family)
    signal_extractor = Agent(
        research_model,
        output_type=family.signal_model(),
        system_prompt=(
            "You are a quantitative research analyst. Extract the core trading signal rules into the "
            "structured schema. Use the source text as the primary evidence. Treat any retrieved "
            "supporting paper context as secondary background only, and do not invent fields not "
            "supported by the source text."
        ),
    )
    prompt = family.build_discovery_prompt(raw_markdown, paper_context)
    extraction_result = await signal_extractor.run(prompt)
    return extract_signal_from_result(extraction_result)


def save_signal(config: DiscoveryConfig, signal: BaseModel) -> None:
    db = lancedb.connect(config.lancedb_path)
    data = [{
        "asset": signal.model_dump().get("asset"),
        "strategy_type": config.family,
        "signal_json": json.dumps(signal.model_dump()),
        "source": os.path.basename(config.source_path),
    }]
    table = db.create_table(config.signal_table, data=data, mode="overwrite")
    print(f"Successfully saved signal to LanceDB table '{table.name}'.")


def save_signal_artifact_for_pipeline(config: DiscoveryConfig, signal: BaseModel, paper_context: str) -> None:
    artifact = SignalArtifact(
        strategy_type=config.family,
        signal=signal.model_dump(),
        source=os.path.basename(config.source_path),
        paper_context=paper_context,
    )
    save_signal_artifact(artifact, path=__import__("pathlib").Path(config.artifact_path))
    print(f"Saved signal artifact to {config.artifact_path}.")


async def main() -> None:
    config = parse_args()

    print("--- Starting Phase 1 & 1.5: Source Acquisition ---")
    is_direct = config.source_path.startswith("http") or os.path.exists(config.source_path)

    raw_markdown = ""
    if is_direct:
        print(f"Crawling direct source: {config.source_path}")
        raw_markdown = await crawl_source_text(config.source_path)
        print(f"Extracted {len(raw_markdown)} characters.\n")
    else:
        print(f"'{config.source_path}' is not a URL/file. Treating as search query.")

    if config.skip_paper_search and is_direct:
        print("Supporting paper search skipped.")
        paper_context = raw_markdown
    else:
        # If we have raw_markdown, build_paper_query_from_source_text is used.
        # Otherwise, the source_path is used as the query directly.
        paper_context, paper_search_result = await fetch_paper_context(config, raw_markdown)
        if not is_direct:
            raw_markdown = paper_context  # Use the search results as the primary source

    print("\n--- Starting Phase 2: Synthesis (PydanticAI) ---")
    signal = await run_signal_extraction(config, raw_markdown, paper_context)
    print("\nExtracted Signal Schema:")
    print(signal)

    print("\n--- Saving to LanceDB ---")
    try:
        save_signal(config, signal)
        save_signal_artifact_for_pipeline(config, signal, paper_context)
    except Exception as exc:
        print(f"Error saving to LanceDB: {exc}")

    print("\n🔌 Discovery phase complete.")


if __name__ == "__main__":
    asyncio.run(main())
