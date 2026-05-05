"""Generic live state vector contract."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LiveStateVector(BaseModel):
    names: list[str] = Field(default_factory=list)
    values: list[float] = Field(default_factory=list)


__all__ = ["LiveStateVector"]
