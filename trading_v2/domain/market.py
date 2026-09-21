# coding: utf-8
"""Market-data domain models independent from any provider SDK."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from trading_v2.domain.base import require_aware_datetime, utc_now
from trading_v2.domain.enums import AssetClass


class InstrumentId(BaseModel):
    """Portable instrument identity used across markets and brokers."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    venue: str
    asset_class: AssetClass

    @field_validator("symbol", "venue")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("instrument symbol and venue cannot be empty")
        if ":" in normalized:
            raise ValueError("instrument symbol and venue cannot contain ':'")
        return normalized

    @computed_field
    @property
    def canonical(self) -> str:
        return f"{self.asset_class.value}:{self.venue}:{self.symbol}"

    def __str__(self) -> str:
        return self.canonical


class Instrument(BaseModel):
    """Tradable instrument metadata."""

    model_config = ConfigDict(frozen=True)

    id: InstrumentId
    display_name: str | None = None
    currency: str | None = None
    price_precision: int = Field(default=2, ge=0, le=12)
    quantity_precision: int = Field(default=0, ge=0, le=12)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else None


class Bar(BaseModel):
    """A time-bounded OHLCV bar in provider-neutral form."""

    model_config = ConfigDict(frozen=True)

    instrument: InstrumentId
    timeframe: str
    open_time: datetime
    close_time: datetime
    open: Decimal = Field(gt=0)
    high: Decimal = Field(gt=0)
    low: Decimal = Field(gt=0)
    close: Decimal = Field(gt=0)
    volume: Decimal = Field(default=Decimal("0"), ge=0)
    turnover: Decimal | None = Field(default=None, ge=0)
    source: str
    is_closed: bool = True
    received_at: datetime = Field(default_factory=utc_now)

    @field_validator("timeframe", "source")
    @classmethod
    def non_empty_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("timeframe and source cannot be empty")
        return normalized

    @field_validator("open_time", "close_time", "received_at")
    @classmethod
    def timezone_required(cls, value: datetime, info) -> datetime:
        return require_aware_datetime(value, info.field_name)

    @model_validator(mode="after")
    def validate_price_range(self) -> "Bar":
        if self.close_time <= self.open_time:
            raise ValueError("close_time must be later than open_time")
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high must be the greatest OHLC price")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low must be the smallest OHLC price")
        return self


class MarketSnapshot(BaseModel):
    """Normalized latest quote and daily market statistics."""

    model_config = ConfigDict(frozen=True)

    instrument: InstrumentId
    last: Decimal = Field(gt=0)
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    prev_close: Decimal = Field(gt=0)
    bid: Decimal | None = None
    ask: Decimal | None = None
    volume: Decimal = Field(default=Decimal("0"), ge=0)
    turnover: Decimal = Field(default=Decimal("0"), ge=0)
    market_time: datetime
    received_at: datetime = Field(default_factory=utc_now)
    source: str
    stale: bool = False

    @field_validator("market_time", "received_at")
    @classmethod
    def timezone_required(cls, value: datetime, info) -> datetime:
        return require_aware_datetime(value, info.field_name)

    @field_validator("source")
    @classmethod
    def source_required(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("source cannot be empty")
        return normalized

    @field_validator("open", "high", "low", "bid", "ask")
    @classmethod
    def optional_prices_must_be_positive(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value <= 0:
            raise ValueError("available market prices must be positive")
        return value

    @model_validator(mode="after")
    def validate_market_range(self) -> "MarketSnapshot":
        comparable = [value for value in (self.open, self.last, self.low) if value is not None]
        if self.high is not None and self.high < max(comparable):
            raise ValueError("high must cover open, low and last")
        comparable = [value for value in (self.open, self.last, self.high) if value is not None]
        if self.low is not None and self.low > min(comparable):
            raise ValueError("low must cover open, high and last")
        if self.bid is not None and self.ask is not None and self.bid > self.ask:
            raise ValueError("bid cannot be greater than ask")
        return self
