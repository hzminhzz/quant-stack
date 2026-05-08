from __future__ import annotations

import polars as pl

from quant_stack.backtesting.polars_engine import _extract_trade_returns


def _legacy_trade_returns(frame: pl.DataFrame) -> list[float]:
    rows = frame.select(["position", "asset_return"]).to_dicts()
    trades: list[float] = []
    current = 1.0
    in_trade = False
    for row in rows:
        position = float(row["position"])
        if position > 0.0:
            in_trade = True
            current *= 1.0 + float(row["asset_return"])
        elif in_trade:
            trades.append(current - 1.0)
            current = 1.0
            in_trade = False
    if in_trade:
        trades.append(current - 1.0)
    return trades


def test_extract_trade_returns_matches_legacy_logic_multiple_trades() -> None:
    frame = pl.DataFrame(
        {
            "position": [0.0, 1.0, 1.0, 0.0, 1.0, 1.0, 1.0, 0.0],
            "asset_return": [0.0, 0.01, -0.02, 0.03, 0.04, 0.0, -0.01, 0.02],
        }
    )
    assert _extract_trade_returns(frame) == _legacy_trade_returns(frame)


def test_extract_trade_returns_handles_open_trade_at_end() -> None:
    frame = pl.DataFrame(
        {
            "position": [0.0, 1.0, 1.0, 1.0],
            "asset_return": [0.0, 0.02, -0.01, 0.03],
        }
    )
    assert _extract_trade_returns(frame) == _legacy_trade_returns(frame)


def test_extract_trade_returns_no_exposure_returns_empty() -> None:
    frame = pl.DataFrame(
        {
            "position": [0.0, 0.0, 0.0],
            "asset_return": [0.01, -0.02, 0.03],
        }
    )
    assert _extract_trade_returns(frame) == []
