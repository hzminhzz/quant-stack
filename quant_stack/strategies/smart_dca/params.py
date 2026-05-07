"""Smart DCA strategy parameters."""

from __future__ import annotations

from pydantic import BaseModel, Field

BUY = 1
SELL = -1

ENGINE_SB = 0
ENGINE_FB = 1
ENGINE_SS = 2
ENGINE_FS = 3
ENGINE_NAMES = ("SB", "FB", "SS", "FS")


class EngineConfig(BaseModel):
    name: str
    enabled: bool
    side: int  # BUY=1, SELL=-1
    base_lot: float = Field(0.01, ge=0)
    min_step: float = Field(0.0, ge=0)
    tp_dist: float = Field(0.0, ge=0)
    max_levels: int = Field(20, ge=1)
    reduce_levels: int = Field(10, ge=1)
    step_factor: float = Field(1.0, ge=0.0)


class SmartDCAParams(BaseModel):
    cooldown_entry_sec: int = Field(10, ge=0)
    cooldown_dca_sec: int = Field(60, ge=0)
    dca_by_last_price: bool = False
    convert_to_xau_factor: float = Field(1.0, gt=0)
    reduce_tp_dist_to_0p5: bool = False

    use_opposite_lock: bool = False
    opposite_lock_level: int = Field(20, ge=1)
    max_total_pnl: float = Field(20000.0, ge=0)

    use_tp_trailing: bool = True
    tp_trailing_step: float = Field(0.1, ge=0)
    tp_trailing_dist: float = Field(1.0, ge=0)

    use_dca_trailing: bool = False
    dca_trailing_step: float = Field(0.1, ge=0)
    dca_trailing_dist: float = Field(1.0, ge=0)

    use_time_filter: bool = True
    start_minute_of_day: int = Field(90, ge=0, le=1440)      # 01:30
    end_minute_of_day: int = Field(1290, ge=0, le=1440)      # 21:30

    use_friday_filter: bool = False
    friday_hard_close_hour: int = Field(23, ge=0, le=23)

    fb_slow_level_start: int = Field(5, ge=1)
    fs_slow_level_start: int = Field(5, ge=1)

    contract_size: float = Field(1.0, gt=0)
    commission_per_lot: float = Field(0.0, ge=0)
    use_bid_as_avr: bool = True

    sb: EngineConfig = EngineConfig(name="SB", enabled=True, side=BUY, base_lot=0.01, min_step=3.0, tp_dist=2.5, max_levels=20, reduce_levels=10, step_factor=1.1)
    fb: EngineConfig = EngineConfig(name="FB", enabled=False, side=BUY, base_lot=0.01, min_step=2.0, tp_dist=2.5, max_levels=20, reduce_levels=16, step_factor=1.2)
    ss: EngineConfig = EngineConfig(name="SS", enabled=False, side=SELL, base_lot=0.01, min_step=5.0, tp_dist=3.5, max_levels=20, reduce_levels=5, step_factor=1.0)
    fs: EngineConfig = EngineConfig(name="FS", enabled=False, side=SELL, base_lot=0.01, min_step=3.5, tp_dist=3.0, max_levels=20, reduce_levels=16, step_factor=1.2)


__all__ = ["EngineConfig", "SmartDCAParams", "BUY", "SELL", "ENGINE_SB", "ENGINE_FB", "ENGINE_SS", "ENGINE_FS", "ENGINE_NAMES"]
