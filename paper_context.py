from __future__ import annotations

from datetime import datetime
import os
import re
from typing import Any

from paper_search_client import PaperSearchMCPClient, search_papers_sync


GENERIC_QUERY_TERMS = {
    "quantitative",
    "trading",
    "strategy",
    "research",
    "backtest",
    "empirical",
    "out",
    "of",
    "sample",
    "transaction",
    "costs",
    "robustness",
    "moving",
    "average",
    "short",
    "long",
    "window",
    "loss",
    "stop",
    "period",
}

ASSET_ALIASES = {
    "BTC": "bitcoin cryptocurrency",
    "ETH": "ethereum cryptocurrency",
    "SOL": "solana cryptocurrency",
    "SPY": "s&p 500 etf equity",
    "QQQ": "nasdaq 100 etf equity",
}

FINANCE_RELEVANCE_TERMS = {
    "trading",
    "finance",
    "financial",
    "market",
    "markets",
    "portfolio",
    "return",
    "returns",
    "asset",
    "assets",
    "stock",
    "stocks",
    "equity",
    "equities",
    "futures",
    "factor",
    "alpha",
    "bitcoin",
    "btc",
    "cryptocurrency",
    "crypto",
}

POSITIVE_EVIDENCE_TERMS = {
    "out-of-sample": 8,
    "out of sample": 8,
    "walk-forward": 7,
    "walk forward": 7,
    "transaction costs": 7,
    "slippage": 6,
    "market impact": 6,
    "net-of-fee": 6,
    "net of fee": 6,
    "benchmark": 4,
    "robustness": 5,
    "robust": 4,
    "sensitivity": 4,
    "cross-validation": 4,
    "cross validation": 4,
    "holdout": 4,
    "backtest": 3,
    "backtesting": 3,
    "empirical": 3,
}

NEGATIVE_EVIDENCE_TERMS = {
    "proceedings": -10,
    "handbook": -8,
    "chapter": -7,
    "survey": -6,
    "tutorial": -6,
    "editorial": -8,
    "workshop": -5,
    "lecture": -6,
    "introduction": -4,
    "corrigendum": -8,
    "erratum": -8,
}

SOURCE_PRIORITY = {
    "crossref": 34,
    "openalex": 33,
    "semantic": 30,
    "ssrn": 24,
    "pubmed": 24,
    "pmc": 22,
    "europepmc": 22,
    "arxiv": 18,
    "core": 10,
    "dblp": 9,
    "openaire": 8,
    "zenodo": 7,
    "hal": 7,
    "doaj": 7,
    "base": 5,
    "citeseerx": 4,
}

DEFAULT_PAPER_SOURCES = "crossref,openalex,semantic,ssrn,arxiv"

WEAK_PROVENANCE_SOURCES = {
    "core",
    "base",
    "citeseerx",
    "openaire",
    "zenodo",
    "hal",
    "doaj",
}

DISCOVERY_KEYWORDS = (
    "strategy",
    "trading",
    "signal",
    "backtest",
    "returns",
    "alpha",
    "momentum",
    "mean reversion",
    "moving average",
    "crossover",
    "stop loss",
    "transaction cost",
    "slippage",
    "execution",
    "volatility",
    "factor",
    "portfolio",
    "market impact",
)


def _normalize_whitespace(text: str) -> str:
    return " ".join(str(text).split())


def normalize_paper_sources(sources: str) -> str:
    requested = [part.strip().lower() for part in sources.split(",") if part.strip()]
    if not requested:
        requested = [part.strip() for part in DEFAULT_PAPER_SOURCES.split(",") if part.strip()]

    unique_requested: list[str] = []
    for source in requested:
        if source not in unique_requested:
            unique_requested.append(source)

    prioritized = sorted(
        unique_requested,
        key=lambda source: (-SOURCE_PRIORITY.get(source, 0), source),
    )
    return ",".join(prioritized)


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]{2,}", text.lower())


def _salient_query_tokens(query: str) -> set[str]:
    return {
        token
        for token in _tokenize(query)
        if token not in GENERIC_QUERY_TERMS and not token.isdigit()
    }


def _build_validation_suffix() -> str:
    return "empirical backtest out-of-sample transaction costs robustness"


def _expand_asset_aliases(text: str) -> str:
    normalized = _normalize_whitespace(text).strip()
    if not normalized:
        return normalized
    alias = ASSET_ALIASES.get(normalized.upper())
    if alias:
        return f"{normalized} {alias}"
    return normalized


def _is_probably_ticker(token: str) -> bool:
    return token.isupper() and token.isalpha() and 2 <= len(token) <= 6


def _extract_tickers(text: str) -> list[str]:
    seen: list[str] = []
    for match in re.findall(r"\b[A-Z]{2,6}\b", text):
        if _is_probably_ticker(match) and match not in seen:
            seen.append(match)
    return seen[:4]


def _extract_window_terms(text: str) -> list[str]:
    matches = re.findall(r"\b\d{1,4}\s*(?:period|day|week|month)?\s*(?:moving average|ema|sma|rsi)\b", text, flags=re.I)
    return [_normalize_whitespace(match.lower()) for match in matches[:4]]


def _pick_relevant_sentences(text: str, max_sentences: int = 2) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", _normalize_whitespace(text))
    scored: list[tuple[int, str]] = []
    for sentence in sentences:
        lower = sentence.lower()
        score = sum(keyword in lower for keyword in DISCOVERY_KEYWORDS)
        if score > 0:
            scored.append((score, sentence[:240]))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [sentence for _, sentence in scored[:max_sentences]]


def _extract_strategy_terms(text: str) -> list[str]:
    lower = _normalize_whitespace(text).lower()
    strategy_terms: list[str] = []
    if "moving average" in lower and ("crosses above" in lower or "crossover" in lower or "crosses below" in lower):
        strategy_terms.append("moving average crossover")
    if "stop loss" in lower:
        strategy_terms.append("stop loss")
    if "mean reversion" in lower:
        strategy_terms.append("mean reversion")
    if "momentum" in lower:
        strategy_terms.append("momentum")
    if "pairs trading" in lower:
        strategy_terms.append("pairs trading")
    return strategy_terms[:4]


def _extract_year(value: str) -> int | None:
    match = re.search(r"(19|20)\d{2}", value)
    if not match:
        return None
    try:
        return int(match.group(0))
    except ValueError:
        return None


def _compute_recency_score(published_date: str) -> int:
    year = _extract_year(published_date)
    if year is None:
        return 0
    current_year = datetime.now().year
    age = current_year - year
    if age <= 2:
        return 6
    if age <= 5:
        return 5
    if age <= 10:
        return 3
    if age <= 20:
        return 1
    return 0


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _text_signal_score(text: str) -> int:
    lower = text.lower()
    score = 0
    for term, weight in POSITIVE_EVIDENCE_TERMS.items():
        if term in lower:
            score += weight
    for term, weight in NEGATIVE_EVIDENCE_TERMS.items():
        if term in lower:
            score += weight
    return score


def _has_finance_context(text: str) -> bool:
    lower = text.lower()
    return any(term in lower for term in FINANCE_RELEVANCE_TERMS)


def _query_relevance_score(query: str, paper: dict[str, Any]) -> int:
    query_tokens = _salient_query_tokens(query)
    if not query_tokens:
        return 0

    searchable = _normalize_whitespace(
        f"{paper.get('title', '')} {paper.get('abstract', '')} {paper.get('authors', '')}"
    ).lower()
    paper_tokens = set(_tokenize(searchable))
    overlap = len(query_tokens & paper_tokens)
    if overlap == 0:
        return -12
    return overlap * 4


def _paper_quality_score(query: str, paper: dict[str, Any]) -> int:
    source = str(paper.get("source", "")).strip().lower()
    doi = str(paper.get("doi", "")).strip()
    citations = _safe_int(paper.get("citations", 0))
    published_date = str(paper.get("published_date", "")).strip()
    text = _normalize_whitespace(f"{paper.get('title', '')} {paper.get('abstract', '')}")

    score = 0
    score += SOURCE_PRIORITY.get(source, 0)
    score += 10 if doi else 0
    score += min(citations, 200) // 10
    score += _compute_recency_score(published_date)
    score += _text_signal_score(text)
    score += _query_relevance_score(query, paper)
    return score


def _paper_identity(paper: dict[str, Any]) -> str:
    doi = str(paper.get("doi", "")).strip().lower()
    if doi:
        return f"doi:{doi}"
    title = _normalize_whitespace(str(paper.get("title", "")).lower())
    return f"title:{title}"


def _is_usable_paper(paper: dict[str, Any]) -> bool:
    title = _normalize_whitespace(str(paper.get("title", "")).strip())
    if not title:
        return False
    text = _normalize_whitespace(f"{title} {paper.get('abstract', '')}").lower()
    if title.lower().startswith(("figure ", "table ")):
        return False
    if any(term in text for term in ("editorial", "corrigendum", "erratum", "proceedings")):
        return False
    if not _has_finance_context(text):
        return False
    source = str(paper.get("source", "")).strip().lower()
    doi = str(paper.get("doi", "")).strip()
    citations = _safe_int(paper.get("citations", 0))
    if source in WEAK_PROVENANCE_SOURCES and not doi and citations <= 0:
        return False
    return True


def _rerank_and_filter_papers(query: str, result: dict[str, Any]) -> dict[str, Any]:
    papers = result.get("papers", []) if isinstance(result, dict) else []
    ranked: list[tuple[int, int, str, dict[str, Any]]] = []
    seen_identities: set[str] = set()

    for paper in papers:
        if not isinstance(paper, dict) or not _is_usable_paper(paper):
            continue
        identity = _paper_identity(paper)
        if identity in seen_identities:
            continue
        seen_identities.add(identity)
        score = _paper_quality_score(query, paper)
        if score < 0:
            continue
        ranked.append((score, -_safe_int(paper.get("citations", 0)), identity, paper))

    ranked.sort(key=lambda item: (-item[0], item[1], item[2]))
    cloned = dict(result)
    cloned["papers"] = [paper for _, _, _, paper in ranked]
    return cloned


def build_paper_query_from_signal(signal_data: dict[str, Any]) -> str:
    asset = _expand_asset_aliases(signal_data.get("asset", "")).strip() or "asset"
    hypothesis = _normalize_whitespace(signal_data.get("hypothesis", signal_data.get("condition", ""))).strip() or "trading signal"
    params = signal_data.get("params", {}) if isinstance(signal_data.get("params"), dict) else {}
    param_terms = []
    for key, value in params.items():
        if value not in (None, ""):
            param_terms.append(f"{key} {value}")
    stop_loss = signal_data.get("stop_loss_pct")
    stop_loss_term = f"stop loss {stop_loss}" if stop_loss not in (None, "") else ""
    query_parts = [asset, hypothesis, " ".join(param_terms), stop_loss_term, _build_validation_suffix()]
    return _normalize_whitespace(" ".join(part for part in query_parts if part))


def build_paper_query_from_source_text(raw_markdown: str, source_path: str) -> str:
    source_name = os.path.splitext(os.path.basename(source_path))[0].replace("_", " ").strip()
    if source_name.isdigit():
        source_name = ""

    normalized_text = _normalize_whitespace(raw_markdown)
    tickers = _extract_tickers(raw_markdown)
    expanded_tickers = [_expand_asset_aliases(ticker) for ticker in tickers]
    window_terms = _extract_window_terms(raw_markdown)
    strategy_terms = _extract_strategy_terms(raw_markdown)
    snippets = _pick_relevant_sentences(normalized_text)

    query_parts = [
        source_name,
        " ".join(expanded_tickers),
        " ".join(strategy_terms),
        " ".join(window_terms),
        " ".join(snippets),
        _build_validation_suffix(),
    ]
    query = _normalize_whitespace(" ".join(part for part in query_parts if part))
    if query:
        return query
    return f"quantitative trading strategy {_build_validation_suffix()}"


def normalize_paper_search_result(raw_result: Any) -> dict[str, Any]:
    if isinstance(raw_result, dict):
        nested_result = raw_result.get("result")
        if isinstance(nested_result, dict):
            return nested_result
        return raw_result
    return {}


def format_paper_context(query: str, result: dict[str, Any], max_papers: int = 5) -> str:
    ranked_result = _rerank_and_filter_papers(query, result)
    papers = ranked_result.get("papers", []) if isinstance(ranked_result, dict) else []
    if not papers:
        return f"No supporting papers found for query: {query}"

    lines = [
        f"Paper search query: {query}",
        f"Sources used: {', '.join(ranked_result.get('sources_used', []))}",
    ]

    for index, paper in enumerate(papers[:max_papers], start=1):
        title = str(paper.get("title", "Untitled")).strip()
        source = str(paper.get("source", "unknown")).strip()
        authors = str(paper.get("authors", "")).strip()
        published_date = str(paper.get("published_date", "")).strip()
        abstract = " ".join(str(paper.get("abstract", "")).split())[:400]
        lines.append(
            f"{index}. {title} | source={source} | authors={authors or 'n/a'} | "
            f"published={published_date or 'n/a'} | abstract={abstract or 'n/a'}"
        )

    return "\n".join(lines)


def print_paper_summary(paper_search_result: dict[str, Any] | None, max_papers: int = 5) -> None:
    if not paper_search_result:
        return

    print("\n--- Supporting Papers Retrieved ---")
    for index, paper in enumerate(paper_search_result.get("papers", [])[:max_papers], start=1):
        print(f"{index}. {paper.get('title', 'Untitled')} [{paper.get('source', 'unknown')}]")


def fetch_paper_context_sync(
    *,
    query: str,
    sources: str,
    year: str | None,
    max_results_per_source: int,
    skip_paper_search: bool,
) -> tuple[str, dict[str, Any] | None]:
    if skip_paper_search:
        return "Paper search skipped by configuration.", None

    normalized_sources = normalize_paper_sources(sources)

    try:
        raw_result = search_papers_sync(
            query=query,
            max_results_per_source=max_results_per_source,
            sources=normalized_sources,
            year=year,
        )
    except Exception as exc:
        return f"Paper search failed: {exc}", None

    result = normalize_paper_search_result(raw_result)
    ranked_result = _rerank_and_filter_papers(query, result)
    return format_paper_context(query, ranked_result), ranked_result


async def fetch_paper_context_async(
    *,
    query: str,
    sources: str,
    year: str | None,
    max_results_per_source: int,
    skip_paper_search: bool,
) -> tuple[str, dict[str, Any] | None]:
    if skip_paper_search:
        return "Paper search skipped by configuration.", None

    normalized_sources = normalize_paper_sources(sources)

    try:
        async with PaperSearchMCPClient() as client:
            raw_result = await client.search_papers(
                query=query,
                max_results_per_source=max_results_per_source,
                sources=normalized_sources,
                year=year,
            )
    except Exception as exc:
        return f"Paper search failed: {exc}", None

    result = normalize_paper_search_result(raw_result)
    ranked_result = _rerank_and_filter_papers(query, result)
    return format_paper_context(query, ranked_result), ranked_result
