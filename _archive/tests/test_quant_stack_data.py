from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import polars as pl

from quant_stack.data import OHLCVValidationError, load_ohlcv_parquet, resample_ohlcv, validate_ohlcv


def _valid_frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "timestamp": [
                "2024-01-01T00:00:00",
                "2024-01-01T00:01:00",
                "2024-01-01T00:02:00",
                "2024-01-01T00:03:00",
            ],
            "open": [100.0, 101.0, 102.0, 103.0],
            "high": [101.0, 102.0, 103.0, 104.0],
            "low": [99.0, 100.0, 101.0, 102.0],
            "close": [100.5, 101.5, 102.5, 103.5],
            "volume": [1.0, 2.0, 3.0, 4.0],
        }
    )


class QuantStackDataTests(unittest.TestCase):
    def test_valid_ohlcv_passes_and_normalizes_timestamp(self) -> None:
        validated = validate_ohlcv(_valid_frame())

        self.assertEqual(validated.schema["timestamp"], pl.Datetime)
        self.assertEqual(validated["close"].to_list(), [100.5, 101.5, 102.5, 103.5])

    def test_epoch_ms_timestamp_is_cast_to_datetime(self) -> None:
        frame = _valid_frame().with_columns(pl.col("timestamp").str.to_datetime().dt.epoch(time_unit="ms"))

        validated = validate_ohlcv(frame)

        self.assertEqual(validated.schema["timestamp"], pl.Datetime)

    def test_null_close_fails(self) -> None:
        frame = _valid_frame().with_columns(pl.when(pl.arange(0, pl.len()) == 1).then(None).otherwise(pl.col("close")).alias("close"))

        with self.assertRaisesRegex(OHLCVValidationError, "close"):
            validate_ohlcv(frame)

    def test_duplicate_timestamp_fails(self) -> None:
        frame = _valid_frame().with_columns(
            pl.when(pl.arange(0, pl.len()) == 1)
            .then(pl.lit("2024-01-01T00:00:00"))
            .otherwise(pl.col("timestamp"))
            .alias("timestamp")
        )

        with self.assertRaisesRegex(OHLCVValidationError, "duplicate"):
            validate_ohlcv(frame)

    def test_unsorted_input_is_sorted_by_default(self) -> None:
        frame = _valid_frame().reverse()

        validated = validate_ohlcv(frame)

        self.assertEqual(validated["close"].to_list(), [100.5, 101.5, 102.5, 103.5])

    def test_negative_volume_fails(self) -> None:
        frame = _valid_frame().with_columns(pl.when(pl.arange(0, pl.len()) == 2).then(-1.0).otherwise(pl.col("volume")).alias("volume"))

        with self.assertRaisesRegex(OHLCVValidationError, "volume"):
            validate_ohlcv(frame)

    def test_invalid_high_low_bounds_fail(self) -> None:
        bad_high = _valid_frame().with_columns(pl.lit(99.0).alias("high"))
        bad_low = _valid_frame().with_columns(pl.lit(105.0).alias("low"))

        with self.assertRaisesRegex(OHLCVValidationError, "high"):
            validate_ohlcv(bad_high)
        with self.assertRaisesRegex(OHLCVValidationError, "low"):
            validate_ohlcv(bad_low)

    def test_resample_1m_to_2m_matches_expected_ohlcv(self) -> None:
        result = resample_ohlcv(_valid_frame(), every="2m")

        self.assertEqual(result["open"].to_list(), [100.0, 102.0])
        self.assertEqual(result["high"].to_list(), [102.0, 104.0])
        self.assertEqual(result["low"].to_list(), [99.0, 101.0])
        self.assertEqual(result["close"].to_list(), [101.5, 103.5])
        self.assertEqual(result["volume"].to_list(), [3.0, 7.0])

    def test_load_ohlcv_parquet_validates_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "ohlcv.parquet"
            _valid_frame().write_parquet(path)

            loaded = load_ohlcv_parquet(path)

        self.assertEqual(loaded.schema["timestamp"], pl.Datetime)
        self.assertEqual(loaded.height, 4)


if __name__ == "__main__":
    unittest.main()
