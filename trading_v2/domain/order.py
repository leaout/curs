# coding: utf-8
"""Order lifecycle model shared by paper and live brokers."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trading_v2.domain.base import require_aware_datetime, utc_now
from trading_v2.domain.enums import OrderSide, OrderStatus, OrderType, TradingMode
from trading_v2.domain.market import InstrumentId


class Order(BaseModel):
    """Local order state; broker-specific payloads stay inside adapters."""

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    client_order_id: str
    broker_order_id: str | None = None
    session_id: UUID
    signal_id: UUID
    decision_id: UUID
    instrument: InstrumentId
    side: OrderSide
    order_type: OrderType
    quantity: Decimal = Field(gt=0)
    limit_price: Decimal | None = Field(default=None, gt=0)
    filled_quantity: Decimal = Field(default=Decimal("0"), ge=0)
    average_fill_price: Decimal | None = Field(default=None, gt=0)
    status: OrderStatus = OrderStatus.CREATED
    mode: TradingMode
    rejection_reason: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("client_order_id")
    @classmethod
    def client_order_id_required(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("client_order_id cannot be empty")
        return normalized

    @field_validator("created_at", "updated_at")
    @classmethod
    def timezone_required(cls, value: datetime, info) -> datetime:
        return require_aware_datetime(value, info.field_name)

    @model_validator(mode="after")
    def validate_order(self) -> "Order":
        if self.order_type == OrderType.LIMIT and self.limit_price is None:
            raise ValueError("limit_price is required for LIMIT orders")
        if self.filled_quantity > self.quantity:
            raise ValueError("filled_quantity cannot exceed quantity")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be earlier than created_at")
        return self
