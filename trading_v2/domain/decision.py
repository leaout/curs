# coding: utf-8
"""Structured model decision contract."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trading_v2.domain.base import require_aware_datetime, utc_now
from trading_v2.domain.enums import DecisionAction, OrderType


class Decision(BaseModel):
    """Validated action proposal returned by a model provider."""

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    signal_id: UUID
    session_id: UUID
    strategy_version: int = Field(ge=1)
    action: DecisionAction
    confidence: float = Field(ge=0, le=1)
    quantity: Decimal = Field(default=Decimal("0"), ge=0)
    order_type: OrderType = OrderType.MARKET
    limit_price: Decimal | None = Field(default=None, gt=0)
    stop_loss: Decimal | None = Field(default=None, gt=0)
    take_profit: Decimal | None = Field(default=None, gt=0)
    rationale: str
    model_provider: str
    model_name: str
    prompt_version: str
    created_at: datetime = Field(default_factory=utc_now)
    valid_until: datetime | None = None

    @field_validator("rationale", "model_provider", "model_name", "prompt_version")
    @classmethod
    def non_empty_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("decision text fields cannot be empty")
        return normalized

    @field_validator("created_at", "valid_until")
    @classmethod
    def timezone_required(cls, value: datetime | None, info) -> datetime | None:
        if value is None:
            return None
        return require_aware_datetime(value, info.field_name)

    @model_validator(mode="after")
    def validate_action(self) -> "Decision":
        if self.action == DecisionAction.HOLD and self.quantity != 0:
            raise ValueError("HOLD decisions must have zero quantity")
        if self.action != DecisionAction.HOLD and self.quantity <= 0:
            raise ValueError("BUY and SELL decisions require a positive quantity")
        if self.order_type == OrderType.LIMIT and self.limit_price is None:
            raise ValueError("limit_price is required for LIMIT decisions")
        if self.valid_until is not None and self.valid_until <= self.created_at:
            raise ValueError("valid_until must be later than created_at")
        return self
