from __future__ import annotations

import unittest

import polars as pl

from quant_stack.intelligence.scoring import rolling_percentile, rolling_zscore, tag_extreme_events


class IntelligenceScoringTests(unittest.TestCase):
    def test_zscore_deterministic(self) -> None:
        df = pl.DataFrame({"value": [1.0, 2.0, 3.0, 4.0, 5.0]})
        one = rolling_zscore(df, value_col="value", window=3)
        two = rolling_zscore(df, value_col="value", window=3)
        self.assertEqual(one.to_dict(as_series=False), two.to_dict(as_series=False))

    def test_percentile_and_extreme_tags(self) -> None:
        df = pl.DataFrame({"value": [1.0, 1.0, 1.0, 10.0, 1.0, 1.0]})
        scored = rolling_zscore(df, value_col="value", window=3)
        scored = rolling_percentile(scored, value_col="value", window=3)
        tagged = tag_extreme_events(scored, zscore_col="value_zscore", threshold=1.0)
        self.assertIn("is_extreme", tagged.columns)


if __name__ == "__main__":
    unittest.main()
