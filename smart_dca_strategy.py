"""
Smart DCA MT5 EA conversion scaffold for quant-stack style research.

Original EA: DCA Multi Engine v3.1 - TP Lock Opposite
Source: SmartDCAV#09.mq5

Design goals:
- deterministic
- no pandas in the core path
- Polars can prepare columns outside; the simulator consumes NumPy arrays
- Numba-compatible state-machine core

Important MT5 parity note:
The EA computes avrPrice = (bidPrice + bidPrice) / 2, so it effectively uses bid,
not mid-price. This implementation preserves that by default with use_bid_as_avr=True.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

try:
    from numba import njit
except Exception:  # pragma: no cover
    njit = None


BUY = 1
SELL = -1

ENGINE_SB = 0
ENGINE_FB = 1
ENGINE_SS = 2
ENGINE_FS = 3
ENGINE_NAMES = ("SB", "FB", "SS", "FS")

FIB_LOTS = np.array(
    [1, 1, 2, 2, 3, 3, 5, 5, 8, 8, 13, 13, 21, 21, 34, 34, 55, 55, 89, 89],
    dtype=np.float64,
)


@dataclass(frozen=True)
class EngineConfig:
    name: str
    enabled: bool
    side: int  # BUY=1, SELL=-1
    base_lot: float
    min_step: float
    tp_dist: float
    max_levels: int
    reduce_levels: int
    step_factor: float


@dataclass(frozen=True)
class SmartDCAConfig:
    cooldown_entry_sec: int = 10
    cooldown_dca_sec: int = 60
    dca_by_last_price: bool = False
    convert_to_xau_factor: float = 1.0
    reduce_tp_dist_to_0p5: bool = False

    use_opposite_lock: bool = False
    opposite_lock_level: int = 20
    max_total_pnl: float = 20000.0

    use_tp_trailing: bool = True
    tp_trailing_step: float = 0.1
    tp_trailing_dist: float = 1.0

    use_dca_trailing: bool = False
    dca_trailing_step: float = 0.1
    dca_trailing_dist: float = 1.0

    use_time_filter: bool = True
    start_minute_of_day: int = 90      # 01:30
    end_minute_of_day: int = 1290      # 21:30

    use_friday_filter: bool = False
    friday_hard_close_hour: int = 23

    fb_slow_level_start: int = 5
    fs_slow_level_start: int = 5

    contract_size: float = 1.0
    commission_per_lot: float = 0.0
    use_bid_as_avr: bool = True

    sb: EngineConfig = EngineConfig("SB", True, BUY, 0.01, 3.0, 2.5, 20, 10, 1.1)
    fb: EngineConfig = EngineConfig("FB", False, BUY, 0.01, 2.0, 2.5, 20, 16, 1.2)
    ss: EngineConfig = EngineConfig("SS", False, SELL, 0.01, 5.0, 3.5, 20, 5, 1.0)
    fs: EngineConfig = EngineConfig("FS", False, SELL, 0.01, 3.5, 3.0, 20, 16, 1.2)


def configs_to_arrays(cfg: SmartDCAConfig) -> Tuple[np.ndarray, ...]:
    engines = (cfg.sb, cfg.fb, cfg.ss, cfg.fs)
    enabled = np.array([e.enabled for e in engines], dtype=np.bool_)
    side = np.array([e.side for e in engines], dtype=np.int64)
    base_lot = np.array([e.base_lot for e in engines], dtype=np.float64)
    min_step = np.array([e.min_step for e in engines], dtype=np.float64)
    tp_dist = np.array([e.tp_dist for e in engines], dtype=np.float64)
    max_levels = np.array([e.max_levels for e in engines], dtype=np.int64)
    reduce_levels = np.array([e.reduce_levels for e in engines], dtype=np.int64)
    step_factor = np.array([e.step_factor for e in engines], dtype=np.float64)
    return enabled, side, base_lot, min_step, tp_dist, max_levels, reduce_levels, step_factor


def _get_lot(level: int, base: float) -> float:
    if level > 19:
        level = 19
    return base * float(FIB_LOTS[level])


def _minute_of_day(ts: np.datetime64) -> int:
    # Assumes timestamp is already in broker/server timezone.
    day_start = ts.astype("datetime64[D]")
    return int((ts - day_start) / np.timedelta64(1, "m"))


def _day_of_week(ts: np.datetime64) -> int:
    # Unix epoch 1970-01-01 was Thursday. Return Monday=1 ... Friday=5 ... Sunday=7.
    days = int(ts.astype("datetime64[D]").astype(np.int64))
    return ((days + 3) % 7) + 1


def simulate_smart_dca(
    timestamps: np.ndarray,
    bid: np.ndarray,
    ask: np.ndarray,
    cfg: SmartDCAConfig = SmartDCAConfig(),
) -> Dict[str, np.ndarray]:
    """
    Pure Python reference simulator. Use this first for correctness/parity.

    Parameters
    ----------
    timestamps:
        np.ndarray of np.datetime64, in broker/server timezone.
    bid, ask:
        float arrays with same length. For OHLCV bar backtests, pass realistic synthetic bid/ask
        from close +/- spread/2, or pass bid=close and ask=close+spread.
    cfg:
        Strategy config copied from the MT5 inputs.

    Returns
    -------
    dict of arrays:
        equity, realized_pnl, open_pnl, net_lot, trade_engine, trade_side,
        trade_action, trade_time_idx, trade_price, trade_lot, trade_reason

    Notes
    -----
    - This matches the EA at aggregated-engine level: each engine's open positions are represented
      by total_lot, total_value, first_price, last_price, and pos_count.
    - It does not model MT5 order rejection, slippage, fill policy, margin liquidation, or broker swaps.
    """
    n = len(bid)
    if not (len(ask) == n and len(timestamps) == n):
        raise ValueError("timestamps, bid, and ask must have the same length")

    enabled, side, base_lot, min_step, tp_dist, max_levels, reduce_levels, step_factor = configs_to_arrays(cfg)

    pos_count = np.zeros(4, dtype=np.int64)
    total_lot = np.zeros(4, dtype=np.float64)
    total_value = np.zeros(4, dtype=np.float64)
    first_price = np.zeros(4, dtype=np.float64)
    last_price = np.zeros(4, dtype=np.float64)
    last_order_t = np.zeros(4, dtype=np.float64)  # seconds from first timestamp; 0 mimics reset/no-position
    sl_price = np.zeros(4, dtype=np.float64)
    dca_price_state = np.zeros(4, dtype=np.float64)
    dd_lock_day = np.zeros(4, dtype=np.int64)

    realized_pnl = np.zeros(n, dtype=np.float64)
    open_pnl = np.zeros(n, dtype=np.float64)
    equity = np.zeros(n, dtype=np.float64)
    net_lot = np.zeros(n, dtype=np.float64)

    trade_time_idx: List[int] = []
    trade_engine: List[int] = []
    trade_side: List[int] = []
    trade_action: List[int] = []  # +1 open, -1 close-all
    trade_price: List[float] = []
    trade_lot: List[float] = []
    trade_reason: List[int] = []
    # reason ids: 1 entry, 2 dca, 3 normal_tp, 4 trailing_tp, 5 lock_tp, 6 friday, 7 max_total_pnl

    start_ts = timestamps[0]
    cum_realized = 0.0

    def now_sec(i: int) -> float:
        return float((timestamps[i] - start_ts) / np.timedelta64(1, "s"))

    def avr(i: int) -> float:
        return float(bid[i]) if cfg.use_bid_as_avr else float((bid[i] + ask[i]) / 2.0)

    def mtm_pnl_for_engine(e: int, price: float) -> float:
        if total_lot[e] <= 0:
            return 0.0
        avg = total_value[e] / total_lot[e]
        if side[e] == BUY:
            return (price - avg) * total_lot[e] * cfg.contract_size
        return (avg - price) * total_lot[e] * cfg.contract_size

    def open_order(i: int, e: int, lot: float, reason: int) -> None:
        px = float(ask[i]) if side[e] == BUY else float(bid[i])
        total_lot[e] += lot
        total_value[e] += lot * px
        pos_count[e] += 1
        if first_price[e] == 0:
            first_price[e] = px
            last_price[e] = px
        else:
            if side[e] == BUY:
                first_price[e] = max(first_price[e], px)
                last_price[e] = min(last_price[e], px)
            else:
                first_price[e] = min(first_price[e], px)
                last_price[e] = max(last_price[e], px)
        last_order_t[e] = now_sec(i)
        trade_time_idx.append(i)
        trade_engine.append(e)
        trade_side.append(side[e])
        trade_action.append(1)
        trade_price.append(px)
        trade_lot.append(lot)
        trade_reason.append(reason)

    def close_all(i: int, e: int, reason: int) -> float:
        nonlocal cum_realized
        if total_lot[e] <= 0:
            return 0.0
        px = float(bid[i]) if side[e] == BUY else float(ask[i])
        avg = total_value[e] / total_lot[e]
        pnl = (px - avg) * total_lot[e] * cfg.contract_size if side[e] == BUY else (avg - px) * total_lot[e] * cfg.contract_size
        pnl -= cfg.commission_per_lot * total_lot[e]
        cum_realized += pnl

        trade_time_idx.append(i)
        trade_engine.append(e)
        trade_side.append(side[e])
        trade_action.append(-1)
        trade_price.append(px)
        trade_lot.append(total_lot[e])
        trade_reason.append(reason)

        pos_count[e] = 0
        total_lot[e] = 0.0
        total_value[e] = 0.0
        first_price[e] = 0.0
        last_price[e] = 0.0
        last_order_t[e] = 0.0  # MT5 BuildStates behaves like this once flat
        sl_price[e] = 0.0
        dca_price_state[e] = 0.0
        return pnl

    def trading_time_allowed(i: int) -> bool:
        if not cfg.use_time_filter:
            return True
        m = _minute_of_day(timestamps[i])
        if cfg.start_minute_of_day <= cfg.end_minute_of_day:
            return cfg.start_minute_of_day <= m <= cfg.end_minute_of_day
        return m >= cfg.start_minute_of_day or m <= cfg.end_minute_of_day

    def is_opposite_max(e: int) -> bool:
        if not cfg.use_opposite_lock:
            return False
        if side[e] == BUY:
            return pos_count[ENGINE_SS] >= cfg.opposite_lock_level or pos_count[ENGINE_FS] >= cfg.opposite_lock_level
        return pos_count[ENGINE_SB] >= cfg.opposite_lock_level or pos_count[ENGINE_FB] >= cfg.opposite_lock_level

    def calc_tp_price(e: int) -> float:
        if total_lot[e] <= 0:
            return 0.0
        avg = total_value[e] / total_lot[e]
        dist = tp_dist[e]
        if cfg.reduce_tp_dist_to_0p5:
            dist -= (tp_dist[e] - 0.5) * pos_count[e] / max_levels[e]
        return avg + dist if side[e] == BUY else avg - dist

    def run_engine(i: int, e: int) -> None:
        if not enabled[e]:
            return
        tsec = now_sec(i)
        px = avr(i)

        if pos_count[e] == 0:
            day = int(str(timestamps[i].astype("datetime64[D]"))[-2:])
            if dd_lock_day[e] > 0:
                if dd_lock_day[e] != day:
                    dd_lock_day[e] = 0
                else:
                    return
            if not trading_time_allowed(i):
                return
            if tsec - last_order_t[e] >= cfg.cooldown_entry_sec:
                if e == ENGINE_FB and enabled[ENGINE_SB] and pos_count[ENGINE_SB] < cfg.fb_slow_level_start:
                    return
                if e == ENGINE_FS and enabled[ENGINE_SS] and pos_count[ENGINE_SS] < cfg.fs_slow_level_start:
                    return
                open_order(i, e, _get_lot(0, base_lot[e]), 1)
                sl_price[e] = 0.0
                dca_price_state[e] = 0.0
            return

        if pos_count[e] >= max_levels[e] or tsec - last_order_t[e] < cfg.cooldown_dca_sec:
            return

        if cfg.dca_by_last_price:
            dca_dist = min_step[e]
            if pos_count[e] > reduce_levels[e]:
                dca_dist += min_step[e] * (pos_count[e] - reduce_levels[e]) * step_factor[e]
            dca_trigger = last_price[e] - dca_dist if side[e] == BUY else last_price[e] + dca_dist
        else:
            if pos_count[e] > reduce_levels[e]:
                dca_dist = min_step[e] * reduce_levels[e]
                for k in range(pos_count[e] - reduce_levels[e]):
                    dca_dist += min_step[e] * k * step_factor[e]
            else:
                dca_dist = min_step[e] * pos_count[e]
            dca_trigger = first_price[e] - dca_dist if side[e] == BUY else first_price[e] + dca_dist

        need_dca = False
        if side[e] == BUY:
            if cfg.use_dca_trailing:
                if (
                    dca_price_state[e] == 0 and px < dca_trigger - cfg.dca_trailing_dist * cfg.convert_to_xau_factor
                ) or (
                    dca_price_state[e] > 0 and px < dca_price_state[e] - cfg.dca_trailing_dist * cfg.convert_to_xau_factor - cfg.dca_trailing_step * cfg.convert_to_xau_factor
                ):
                    dca_price_state[e] = px + cfg.dca_trailing_dist * cfg.convert_to_xau_factor
                if dca_price_state[e] > 0 and px > dca_price_state[e]:
                    need_dca = True
            else:
                need_dca = px < dca_trigger
        else:
            if cfg.use_dca_trailing:
                if (
                    dca_price_state[e] == 0 and px > dca_trigger + cfg.dca_trailing_dist * cfg.convert_to_xau_factor
                ) or (
                    dca_price_state[e] > 0 and px > dca_price_state[e] + cfg.dca_trailing_dist * cfg.convert_to_xau_factor + cfg.dca_trailing_step * cfg.convert_to_xau_factor
                ):
                    dca_price_state[e] = px - cfg.dca_trailing_dist * cfg.convert_to_xau_factor
                if dca_price_state[e] > 0 and px < dca_price_state[e]:
                    need_dca = True
            else:
                need_dca = px > dca_trigger

        if need_dca:
            open_order(i, e, _get_lot(int(pos_count[e]), base_lot[e]), 2)
            dca_price_state[e] = 0.0

    def check_tp_normal(i: int, e: int) -> None:
        if total_lot[e] <= 0 or is_opposite_max(e):
            return
        px = avr(i)
        tp = calc_tp_price(e)
        trailing_allowed = cfg.use_tp_trailing and e not in (ENGINE_FB, ENGINE_FS) and pos_count[e] > 1 and pos_count[e] < reduce_levels[e]
        if side[e] == BUY:
            if trailing_allowed:
                if (sl_price[e] == 0 and px > tp + cfg.tp_trailing_dist * cfg.convert_to_xau_factor) or (
                    sl_price[e] > 0 and px > sl_price[e] + cfg.tp_trailing_dist * cfg.convert_to_xau_factor + cfg.tp_trailing_step * cfg.convert_to_xau_factor
                ):
                    sl_price[e] = px - cfg.tp_trailing_dist * cfg.convert_to_xau_factor
                if sl_price[e] > 0 and px < sl_price[e]:
                    close_all(i, e, 4)
            elif px > tp:
                close_all(i, e, 3)
        else:
            if trailing_allowed:
                if (sl_price[e] == 0 and px < tp - cfg.tp_trailing_dist * cfg.convert_to_xau_factor) or (
                    sl_price[e] > 0 and px < sl_price[e] - cfg.tp_trailing_dist * cfg.convert_to_xau_factor - cfg.tp_trailing_step * cfg.convert_to_xau_factor
                ):
                    sl_price[e] = px + cfg.tp_trailing_dist * cfg.convert_to_xau_factor
                if sl_price[e] > 0 and px > sl_price[e]:
                    close_all(i, e, 4)
            elif px < tp:
                close_all(i, e, 3)

    def check_tp_slow_with_fast(i: int, slow: int, fast: int) -> None:
        if total_lot[slow] <= 0 or is_opposite_max(slow):
            return
        if pos_count[fast] < max_levels[fast]:
            check_tp_normal(i, slow)
            return
        combined_lot = total_lot[fast] + total_lot[slow]
        if combined_lot <= 0:
            return
        avg = (total_value[fast] + total_value[slow]) / combined_lot
        px = avr(i)
        if side[slow] == BUY and px >= avg + tp_dist[slow]:
            close_all(i, fast, 5)
            close_all(i, slow, 5)
        elif side[slow] == SELL and px <= avg - tp_dist[slow]:
            close_all(i, fast, 5)
            close_all(i, slow, 5)

    for i in range(n):
        px = avr(i)

        if cfg.use_friday_filter and _day_of_week(timestamps[i]) == 5:
            hour = _minute_of_day(timestamps[i]) // 60
            if hour >= cfg.friday_hard_close_hour and np.sum(pos_count) > 0:
                for e in (ENGINE_SB, ENGINE_FB, ENGINE_SS, ENGINE_FS):
                    close_all(i, e, 6)
                realized_pnl[i] = cum_realized
                equity[i] = cum_realized
                continue

        total_open = sum(mtm_pnl_for_engine(e, px) for e in range(4))
        if cfg.max_total_pnl > 0 and total_open < -cfg.max_total_pnl:
            buy_pnl = mtm_pnl_for_engine(ENGINE_FB, px) + mtm_pnl_for_engine(ENGINE_SB, px)
            sell_pnl = mtm_pnl_for_engine(ENGINE_FS, px) + mtm_pnl_for_engine(ENGINE_SS, px)
            day = int(str(timestamps[i].astype("datetime64[D]"))[-2:])
            if buy_pnl < sell_pnl:
                close_all(i, ENGINE_FB, 7)
                close_all(i, ENGINE_SB, 7)
                dd_lock_day[ENGINE_FB] = day
                dd_lock_day[ENGINE_SB] = day
            else:
                close_all(i, ENGINE_FS, 7)
                close_all(i, ENGINE_SS, 7)
                dd_lock_day[ENGINE_FS] = day
                dd_lock_day[ENGINE_SS] = day
        else:
            # Same order as MT5 OnTick.
            run_engine(i, ENGINE_FB)
            check_tp_normal(i, ENGINE_FB)
            run_engine(i, ENGINE_SB)
            check_tp_slow_with_fast(i, ENGINE_SB, ENGINE_FB)
            run_engine(i, ENGINE_FS)
            check_tp_normal(i, ENGINE_FS)
            run_engine(i, ENGINE_SS)
            check_tp_slow_with_fast(i, ENGINE_SS, ENGINE_FS)

        cur_open = sum(mtm_pnl_for_engine(e, px) for e in range(4))
        open_pnl[i] = cur_open
        realized_pnl[i] = cum_realized
        equity[i] = cum_realized + cur_open
        net_lot[i] = sum(total_lot[e] * side[e] for e in range(4))

    return {
        "equity": equity,
        "realized_pnl": realized_pnl,
        "open_pnl": open_pnl,
        "net_lot": net_lot,
        "trade_time_idx": np.asarray(trade_time_idx, dtype=np.int64),
        "trade_engine": np.asarray(trade_engine, dtype=np.int64),
        "trade_side": np.asarray(trade_side, dtype=np.int64),
        "trade_action": np.asarray(trade_action, dtype=np.int64),
        "trade_price": np.asarray(trade_price, dtype=np.float64),
        "trade_lot": np.asarray(trade_lot, dtype=np.float64),
        "trade_reason": np.asarray(trade_reason, dtype=np.int64),
    }


def prepare_from_polars(df, *, bid_col: str = "bid", ask_col: str = "ask", time_col: str = "timestamp"):
    """Small adapter. Keeps Polars outside the simulator core."""
    return (
        df[time_col].to_numpy(),
        df[bid_col].to_numpy().astype(np.float64),
        df[ask_col].to_numpy().astype(np.float64),
    )


REASON_LABELS = {
    1: "entry",
    2: "dca",
    3: "normal_tp",
    4: "trailing_tp",
    5: "lock_tp",
    6: "friday_close",
    7: "max_total_pnl_close",
}
