"""CLI for DuckDB analytical-layer SQL with Polars output."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import cast

from quant_stack.data.duckdb_layer import run_duckdb_query_to_polars


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run DuckDB SQL for analytical data prep and export to parquet",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    _ = parser.add_argument("--query", required=True, help="DuckDB SQL query to run")
    _ = parser.add_argument(
        "--database-path",
        default=None,
        help="Persistent DuckDB file path (defaults to in-memory)",
    )
    _ = parser.add_argument(
        "--memory-limit",
        default=None,
        help="DuckDB memory_limit setting (e.g. 4GB)",
    )
    _ = parser.add_argument(
        "--temp-directory",
        default=None,
        help="DuckDB temp_directory for spill-to-disk",
    )
    _ = parser.add_argument(
        "--threads",
        type=int,
        default=None,
        help="DuckDB execution threads",
    )
    _ = parser.add_argument(
        "--output-path",
        default=None,
        help="Optional parquet output path for query result",
    )
    _ = parser.add_argument(
        "--show",
        type=int,
        default=10,
        help="Rows to print as preview (0 to skip)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    query = cast(str, args.query)
    database_path = cast(str | None, args.database_path)
    memory_limit = cast(str | None, args.memory_limit)
    temp_directory = cast(str | None, args.temp_directory)
    threads = cast(int | None, args.threads)
    output_path = cast(str | None, args.output_path)
    show = cast(int, args.show)

    result = run_duckdb_query_to_polars(
        query,
        database_path=database_path,
        memory_limit=memory_limit,
        temp_directory=temp_directory,
        threads=threads,
    )

    print(f"Rows: {result.height:,}")
    print(f"Columns: {result.width}")

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        result.write_parquet(out)
        print(f"Saved parquet: {out}")

    if show > 0:
        print("Preview:")
        print(result.head(show))


if __name__ == "__main__":
    main()
