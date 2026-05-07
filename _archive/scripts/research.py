"""DEPRECATED compatibility entrypoint.

This root-level research flow is kept for backward compatibility and historical use.
New reusable research workflow development should prefer `quant_stack/research/`
and canonical package-first entrypoints.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import Any

import dspy
import duckdb
import polars as pl

from evolution.research_guard import guard_research_code
from evolution.schemas import ResearchGuardReport
from paper_context import (
    DEFAULT_PAPER_SOURCES,
    fetch_paper_context_sync,
    print_paper_summary,
)
from pipeline_artifacts import (
    DEFAULT_RESEARCH_ARTIFACT_PATH,
    DEFAULT_SIGNAL_ARTIFACT_PATH,
    ResearchArtifact,
    load_signal_artifact,
    save_research_artifact,
)
from strategy_families import get_strategy_family


DEFAULT_MARKET_DATA_PATH = "Data/Binance/BTC_1m_2025.parquet"
class GeneratePolarsScript(dspy.Signature):
    """
    You are a quant engineer.

    You are given a structured trading signal plus supporting academic paper context.
    Use that context to write a Python script using Polars to backtest the idea on a
    DataFrame `df` with columns: timestamp, open, high, low, close, volume.

    Return ONLY valid python code that defines:
    `def backtest_signal(df: pl.DataFrame) -> float:`

    The function should encode the signal logic faithfully, keep the implementation
    realistic, and return a mock hit-rate or total return metric.
    """

    strategy_type = dspy.InputField(desc="The strategy family to implement")
    signal_summary = dspy.InputField(desc="The extracted signal or hypothesis summary")
    paper_context = dspy.InputField(desc="Concise context from related academic papers")
    polars_code = dspy.OutputField(desc="Valid Python code using Polars")


@dataclass
class ResearchConfig:
    signal_artifact_path: str
    research_artifact_path: str
    data_path: str
    paper_sources: str
    paper_year: str | None
    paper_max_results: int
    skip_paper_search: bool


def parse_args() -> ResearchConfig:
    parser = argparse.ArgumentParser(description="Phase 3 research flow with local paper-search MCP support")
    parser.add_argument("--signal-artifact-path", default=str(DEFAULT_SIGNAL_ARTIFACT_PATH))
    parser.add_argument("--research-artifact-path", default=str(DEFAULT_RESEARCH_ARTIFACT_PATH))
    parser.add_argument("--data-path", default=DEFAULT_MARKET_DATA_PATH)
    parser.add_argument("--paper-sources", default=DEFAULT_PAPER_SOURCES)
    parser.add_argument("--paper-year", default=None)
    parser.add_argument("--paper-max-results", type=int, default=2)
    parser.add_argument("--skip-paper-search", action="store_true")
    args = parser.parse_args()

    return ResearchConfig(
        signal_artifact_path=args.signal_artifact_path,
        research_artifact_path=args.research_artifact_path,
        data_path=args.data_path,
        paper_sources=args.paper_sources,
        paper_year=args.paper_year,
        paper_max_results=args.paper_max_results,
        skip_paper_search=args.skip_paper_search,
    )


def load_signal_for_research(signal_artifact_path: str):
    return load_signal_artifact(path=__import__("pathlib").Path(signal_artifact_path))


def build_signal_summary(strategy_type: str, signal_data: dict[str, Any]) -> str:
    family = get_strategy_family(strategy_type)
    return family.build_seed_hint(signal_data)


def fetch_paper_context(config: ResearchConfig, signal_data: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    family = get_strategy_family(signal_data.get("strategy_type", "rsi")) if "strategy_type" in signal_data else None
    if family is None:
        raise RuntimeError("Signal data missing strategy_type for family-aware paper query.")
    query = family.build_paper_query(signal_data)
    return fetch_paper_context_sync(
        query=query,
        sources=config.paper_sources,
        year=config.paper_year,
        max_results_per_source=config.paper_max_results,
        skip_paper_search=config.skip_paper_search,
    )


def configure_dspy() -> None:
    lm = dspy.LM(
        "openai/gpt-5.4",
        api_key="anything",
        api_base="http://127.0.0.1:8000/v1",
    )
    dspy.configure(lm=lm)


def generate_polars_script(strategy_type: str, signal_data: dict[str, Any], paper_context: str) -> str:
    generator = dspy.Predict(GeneratePolarsScript)
    prediction = generator(
        strategy_type=strategy_type,
        signal_summary=build_signal_summary(strategy_type, signal_data),
        paper_context=paper_context,
    )
    return prediction.polars_code


def save_research_artifact_for_pipeline(
    config: ResearchConfig,
    strategy_type: str,
    signal_data: dict[str, Any],
    paper_context: str,
    polars_code: str,
    guard_report: ResearchGuardReport | None = None,
) -> None:
    artifact = ResearchArtifact(
        version="1.0",
        strategy_type=strategy_type,
        signal=signal_data,
        paper_context=paper_context,
        polars_code=polars_code,
        guard_report=guard_report,
    )
    save_research_artifact(artifact, path=__import__("pathlib").Path(config.research_artifact_path))


def load_market_data(data_path: str) -> pl.DataFrame | None:
    if not os.path.exists(data_path):
        return None

    query = f"""
        SELECT timestamp, open, high, low, close, volume
        FROM read_parquet('{data_path}')
        ORDER BY timestamp ASC
    """
    with duckdb.connect() as con:
        return con.sql(query).pl()


def main() -> None:
    config = parse_args()

    print("--- 1. Retrieving Signal Artifact ---")
    try:
        signal_artifact = load_signal_for_research(config.signal_artifact_path)
        signal_data = dict(signal_artifact.signal)
        signal_data["strategy_type"] = signal_artifact.strategy_type
    except Exception as exc:
        print(f"Error reading signal artifact. Did you run discovery.py first? Details: {exc}")
        return

    print("Found signal:", signal_data)
    print("Strategy family:", signal_artifact.strategy_type)

    print("\n--- 2. Searching Supporting Papers ---")
    paper_context, paper_search_result = fetch_paper_context(config, signal_data)
    print(paper_context)
    print_paper_summary(paper_search_result)

    print("\n--- 3. Setting up DSPy ---")
    configure_dspy()

    print("\n--- 4. Generating Polars Backtest Script ---")
    polars_code = generate_polars_script(signal_artifact.strategy_type, signal_data, paper_context)
    print("\n--- DSPy Generated Polars Script ---")
    print(polars_code)

    print("\n--- 5. Guarding Generated Research Code ---")
    guard_report = guard_research_code(polars_code, strategy_type=signal_artifact.strategy_type)
    if not guard_report.passed:
        print(f"Research guard failed: {guard_report.summary}")
        return

    save_research_artifact_for_pipeline(
        config,
        signal_artifact.strategy_type,
        signal_data,
        paper_context,
        polars_code,
        guard_report=guard_report,
    )

    print("\n--- 6. Data Loading via DuckDB -> Polars ---")
    df_market = load_market_data(config.data_path)
    if df_market is None:
        print(f"Data file {config.data_path} not found. Make sure you downloaded the data.")
        return

    print(f"Loaded {len(df_market)} rows of {signal_data.get('asset', 'asset')} data via Zero-Copy Arrow transfer!")
    print(f"Research artifact saved to {config.research_artifact_path}")
    print("\nPhase 3 Complete! The research flow now grounds strategy generation in supporting literature.")


if __name__ == "__main__":
    main()
