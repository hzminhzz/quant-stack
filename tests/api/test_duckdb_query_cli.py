from __future__ import annotations

from pathlib import Path

import polars as pl

from quant_stack.cli.main import main as cli_main


def test_duckdb_query_cli_writes_output(tmp_path: Path) -> None:
    data_path = tmp_path / "candles.parquet"
    out_path = tmp_path / "out" / "result.parquet"
    frame = pl.DataFrame(
        {
            "timestamp": [1, 2, 3],
            "close": [10.0, 20.0, 30.0],
        }
    )
    frame.write_parquet(data_path)

    query = f"SELECT * FROM read_parquet('{data_path.as_posix()}') WHERE close >= 20 ORDER BY close"
    code = cli_main(
        [
            "duckdb-query",
            "--query",
            query,
            "--output-path",
            out_path.as_posix(),
            "--show",
            "0",
            "--threads",
            "1",
        ]
    )
    assert code == 0
    assert out_path.exists()

    loaded = pl.read_parquet(out_path)
    assert loaded.height == 2
    assert loaded["close"].to_list() == [20.0, 30.0]
