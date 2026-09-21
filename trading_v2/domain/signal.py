# coding: utf-8
"""Candidate trading signal contract."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trading_v2.domain.base import require_aware_datetime, utc_now
from trading_v2.domain.enums import SignalSide
from trading_v2.domain.market import InstrumentId


class Signal(BaseModel):
    """A deterministic trigger that may request one model decision."""

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    strategy_version: int = Field(ge=1)
    instrument: InstrumentId
    timeframe: str
    side: SignalSide
    strength: float = Field(ge=0, le=1)
    reason: str
    bar_time: datetime
    indicators: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime | None = None

    @field_validator("timeframe", "reason")
    @classmethod
    def non_empty_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("timeframe and reason cannot be empty")
        return normalized

    @field_validator("bar_time", "created_at", "expires_at")
    @classmethod
    def timezone_required(cls, value: datetime | None, info) -> datetime | None:
        if value is None:
            return None
        return require_aware_datetime(value, info.field_name)

    @model_validator(mode="after")
    def validate_expiry(self) -> "Signal":
        if self.expires_at is not None and self.expires_at <= self.created_at:
            raise ValueError("expires_at must be later than created_at")
        return self
