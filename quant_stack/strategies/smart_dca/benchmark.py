"""Benchmark harness for Smart DCA simulator contract path."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass

import numpy as np

from quant_stack.strategies.smart_dca.params import SmartDCAParams
from quant_stack.strategies.smart_dca.simulator import simulate_smart_dca, simulate_smart_dca_contract


@dataclass(frozen=True)
class SmartDCABenchmarkResult:
    rows: int
    legacy_seconds: float
    contract_seconds: float
    speed_ratio_contract_over_legacy: float
    trade_count: int
    trade_capacity: int


def _synthetic_inputs(n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    timestamps = np.datetime64("2026-01-01T00:00:00") + np.arange(0, n * 60 * 1000, 60 * 1000, dtype="timedelta64[ms]")
    bid = 2000.0 + 8.0 * np.sin(np.linspace(0.0, 6.0 * np.pi, n))
    ask = bid + 0.5
    return timestamps, bid.astype(np.float64), ask.astype(np.float64)


def run_benchmark(*, rows: int = 50_000, extra_trade_capacity: int = 5_000) -> SmartDCABenchmarkResult:
    """Benchmark legacy simulator output vs preallocated contract output."""

    cfg = SmartDCAParams.model_validate({"use_time_filter": False})
    timestamps, bid, ask = _synthetic_inputs(rows)

    t0 = time.perf_counter()
    legacy = simulate_smart_dca(timestamps, bid, ask, cfg)
    t1 = time.perf_counter()

    t2 = time.perf_counter()
    contract = simulate_smart_dca_contract(
        timestamps,
        bid,
        ask,
        cfg,
        extra_trade_capacity=extra_trade_capacity,
    )
    t3 = time.perf_counter()

    legacy_seconds = t1 - t0
    contract_seconds = t3 - t2
    ratio = contract_seconds / legacy_seconds if legacy_seconds > 0 else float("inf")

    # Quick parity spot-check
    roundtrip = contract.to_legacy_dict()
    np.testing.assert_array_equal(legacy["equity"], roundtrip["equity"])
    np.testing.assert_array_equal(legacy["trade_time_idx"], roundtrip["trade_time_idx"])

    return SmartDCABenchmarkResult(
        rows=rows,
        legacy_seconds=legacy_seconds,
        contract_seconds=contract_seconds,
        speed_ratio_contract_over_legacy=ratio,
        trade_count=contract.trade_count,
        trade_capacity=contract.trade_capacity,
    )


def main() -> None:
    result = run_benchmark()
    payload = asdict(result)
    print(payload)


if __name__ == "__main__":
    main()
