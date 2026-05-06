"""CLI for building canonical Bybit market datasets."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

from quant_stack.data.datasets import BybitDatasetConfig, build_bybit_market_dataset


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build canonical Bybit market dataset")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--timeframe", default="1m")
    parser.add_argument("--start", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD")
    parser.add_argument("--output-dir", default="data/datasets/bybit/market")
    return parser.parse_args(argv)


def _parse_utc_datetime(raw: str) -> datetime:
    value = datetime.fromisoformat(raw)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    start = _parse_utc_datetime(args.start)
    end = _parse_utc_datetime(args.end)
    config = BybitDatasetConfig(
        symbol=args.symbol,
        timeframe=args.timeframe,
        start=start,
        end=end,
        output_dir=args.output_dir,
    )
    result = build_bybit_market_dataset(config)
    print(f"dataset: {result.dataset_path}")
    print(f"metadata: {result.metadata_path}")
    print(f"qa_report: {result.qa_report_path}")


if __name__ == "__main__":
    main()
