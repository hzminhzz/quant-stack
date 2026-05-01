from __future__ import annotations

import unittest

from paper_context import (
    DEFAULT_PAPER_SOURCES,
    build_paper_query_from_signal,
    build_paper_query_from_source_text,
    format_paper_context,
    normalize_paper_sources,
    normalize_paper_search_result,
)


class PaperContextTests(unittest.TestCase):
    def test_normalize_nested_result(self) -> None:
        raw = {"result": {"papers": [{"title": "A"}]}, "ignored": True}
        normalized = normalize_paper_search_result(raw)
        self.assertEqual(normalized, {"papers": [{"title": "A"}]})

    def test_build_signal_query_adds_validation_terms(self) -> None:
        query = build_paper_query_from_signal(
            {
                "asset": "BTC",
                "hypothesis": "moving average crossover",
                "params": {
                    "short_sma": 20,
                    "long_sma": 50,
                    "rsi_period": 14,
                },
                "stop_loss_pct": 2.5,
            }
        )
        self.assertIn("BTC", query)
        self.assertIn("out-of-sample", query)
        self.assertIn("transaction costs", query)
        self.assertIn("stop loss 2.5", query)
        self.assertIn("short_sma 20", query)

    def test_build_source_text_query_prefers_relevant_terms(self) -> None:
        text = (
            "This paper presents a BTC trading strategy. "
            "A 20 period moving average crosses above a 50 period moving average. "
            "We evaluate transaction costs and out-of-sample robustness."
        )
        query = build_paper_query_from_source_text(text, "mock_paper.html")
        self.assertIn("BTC", query)
        self.assertIn("20 period moving average", query)
        self.assertIn("transaction costs", query)

    def test_format_paper_context_reranks_and_filters_noise(self) -> None:
        result = {
            "sources_used": ["core", "crossref", "semantic"],
            "papers": [
                {
                    "title": "Proceedings of an education conference",
                    "source": "core",
                    "authors": "A",
                    "published_date": "2024-01-01",
                    "abstract": "education proceedings",
                    "doi": "",
                    "citations": 0,
                },
                {
                    "title": "Robust Backtesting of BTC Momentum With Transaction Costs",
                    "source": "semantic",
                    "authors": "B",
                    "published_date": "2021-01-01",
                    "abstract": "An empirical out-of-sample backtest with transaction costs and robustness checks for BTC momentum.",
                    "doi": "10.1000/test",
                    "citations": 42,
                },
            ],
        }
        context = format_paper_context("BTC momentum out-of-sample transaction costs", result)
        lines = context.splitlines()
        self.assertIn("Robust Backtesting of BTC Momentum With Transaction Costs", lines[2])
        self.assertNotIn("Proceedings of an education conference", context)

    def test_normalize_paper_sources_prefers_stronger_sources(self) -> None:
        normalized = normalize_paper_sources("core,arxiv,crossref,semantic,openalex")
        self.assertEqual(normalized, "crossref,openalex,semantic,arxiv,core")

    def test_default_source_policy_prefers_provenance_sources(self) -> None:
        self.assertEqual(DEFAULT_PAPER_SOURCES, "crossref,openalex,semantic,ssrn,arxiv")


if __name__ == "__main__":
    unittest.main()
