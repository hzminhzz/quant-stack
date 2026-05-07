"""Cheap data inspection - outputs metadata only, not full data."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import polars as pl


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect OHLCV data without loading full file into context",
    )
    parser.add_argument("data_path", help="Path to parquet file")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    return parser.parse_args(argv)


def inspect_parquet(path: str) -> dict:
    df = pl.scan_parquet(path)
    schema = df.collect_schema()
    stats = df.select([
        pl.len().alias("rows"),
        pl.col("timestamp").min().alias("min_timestamp"),
        pl.col("timestamp").max().alias("max_timestamp"),
    ]).collect()

    row_count = stats.item(0, 0)
    min_ts = stats.item(0, 1)
    max_ts = stats.item(0, 2)

    def fmt_ts(val):
        if val is None:
            return None
        if isinstance(val, datetime):
            return val.isoformat()
        if isinstance(val, int):
            return datetime.fromtimestamp(val / 1000).isoformat()
        return str(val)

    return {
        "path": path,
        "rows": row_count,
        "columns": list(schema.keys()),
        "dtypes": {k: str(v) for k, v in schema.items()},
        "start": fmt_ts(min_ts),
        "end": fmt_ts(max_ts),
    }


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    result = inspect_parquet(args.data_path)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Path: {result['path']}")
        print(f"Rows: {result['rows']:,}")
        print(f"Start: {result['start']}")
        print(f"End: {result['end']}")
        print(f"Columns: {result['columns']}")


if __name__ == "__main__":
    main()