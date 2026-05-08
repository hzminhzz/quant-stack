from __future__ import annotations

import numpy as np

from quant_stack.strategies.smart_dca.params import SmartDCAParams
from quant_stack.strategies.smart_dca.simulator import simulate_smart_dca, simulate_smart_dca_contract


def _synthetic_inputs(n: int = 200) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    timestamps = np.datetime64("2026-01-01T00:00:00") + np.arange(0, n * 60 * 1000, 60 * 1000, dtype="timedelta64[ms]")
    bid = 2000.0 + 5.0 * np.sin(np.linspace(0.0, 4.0 * np.pi, n))
    ask = bid + 0.5
    return timestamps, bid.astype(np.float64), ask.astype(np.float64)


def test_contract_roundtrip_matches_legacy_output() -> None:
    timestamps, bid, ask = _synthetic_inputs(240)
    cfg = SmartDCAParams.model_validate({"use_time_filter": False})

    legacy = simulate_smart_dca(timestamps, bid, ask, cfg)
    contract = simulate_smart_dca_contract(timestamps, bid, ask, cfg, extra_trade_capacity=128)
    roundtrip = contract.to_legacy_dict()

    assert contract.trade_capacity >= contract.trade_count
    for key in legacy:
        np.testing.assert_array_equal(legacy[key], roundtrip[key])


def test_contract_extra_capacity_is_applied() -> None:
    timestamps, bid, ask = _synthetic_inputs(120)
    cfg = SmartDCAParams.model_validate({"use_time_filter": False})

    contract = simulate_smart_dca_contract(timestamps, bid, ask, cfg, extra_trade_capacity=64)
    assert contract.trade_capacity >= contract.trade_count + 64
