"""Forced-flow proxy band reclaim strategy parameters."""

from __future__ import annotations

from pydantic import BaseModel, model_validator


class ForcedFlowBandReclaimParams(BaseModel):
    use_strict_reclaim: bool = True
    require_forced_flow_proxy: bool = True
    require_oi_flush: bool = False
    require_funding_filter: bool = False
    require_basis_filter: bool = False
    max_spread_bps: float | None = None
    exit_at_mid_band: bool = True
    use_context_filters: bool = True

    @model_validator(mode="after")
    def check_spread_threshold(self) -> "ForcedFlowBandReclaimParams":
        if self.max_spread_bps is not None and self.max_spread_bps < 0:
            raise ValueError("max_spread_bps must be non-negative")
        return self


__all__ = ["ForcedFlowBandReclaimParams"]
