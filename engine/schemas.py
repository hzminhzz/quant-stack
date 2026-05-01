from pydantic import BaseModel, Field, field_validator
from typing import Optional

class PropFirmContract(BaseModel):
    cumulative_return: float
    cagr: float
    time_in_market: float
    max_drawdown: float
    max_daily_drawdown: float
    max_consecutive_losing_days: int
    smart_sharpe: float
    smart_sortino: float
    tail_ratio: float
    gain_pain_ratio: float
    kelly_criterion: float
    
    status: Optional[str] = "STATUS: PASSED"

    @field_validator('max_daily_drawdown')
    def check_daily_drawdown(cls, v):
        if v < -0.08:
            raise ValueError(f"Daily Drawdown of {v:.2%} exceeds -8.00% limit.")
        return v

    @field_validator('max_drawdown')
    def check_max_drawdown(cls, v):
        if v < -0.16:
            raise ValueError(f"Max Drawdown of {v:.2%} exceeds -16.00% limit.")
        return v
