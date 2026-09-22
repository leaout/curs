# coding: utf-8
"""Strict structured strategy schema produced by language models."""

from decimal import Decimal
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trading_v2.domain.enums import AssetClass


class RuleOperator(str, Enum):
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    CROSS_ABOVE = "cross_above"
    CROSS_BELOW = "cross_below"


class StrategyRule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    indicator: Literal[
        "close", "open", "high", "low", "volume", "volume_ratio",
        "ma", "ema", "rsi", "macd", "atr", "vwap",
    ]
    operator: RuleOperator
    value: Decimal | None = None
    compare_to: str | None = None
    params: dict[str, int | float | str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_comparison_target(self) -> "StrategyRule":
        if self.value is None and not self.compare_to:
            raise ValueError("a rule requires value or compare_to")
        return self


class StrategyRisk(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    max_position_pct: Decimal = Field(default=Decimal("0.05"), gt=0, le=1)
    stop_loss_pct: Decimal | None = Field(default=None, gt=0, le=1)
    take_profit_pct: Decimal | None = Field(default=None, gt=0, le=10)
    max_daily_loss_pct: Decimal = Field(default=Decimal("0.02"), gt=0, le=1)


class StrategySpec(BaseModel):
    """Allowlisted strategy representation; never executable source code."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=80)
    thesis: str = Field(min_length=1, max_length=500)
    instrument: str
    timeframe: Literal["1m", "5m", "15m", "30m", "1h", "1d"]
    entry_rules: list[StrategyRule] = Field(min_length=1, max_length=20)
    exit_rules: list[StrategyRule] = Field(default_factory=list, max_length=20)
    risk: StrategyRisk = Field(default_factory=StrategyRisk)

    @field_validator("instrument")
    @classmethod
    def validate_instrument(cls, value: str) -> str:
        normalized = value.strip()
        parts = normalized.split(":")
        if len(parts) != 3:
            raise ValueError("instrument must be asset_class:venue:symbol")
        asset_class, venue, symbol = parts
        AssetClass(asset_class.lower())
        if not venue.strip() or not symbol.strip():
            raise ValueError("instrument venue and symbol cannot be empty")
        return f"{asset_class.lower()}:{venue.upper()}:{symbol.upper()}"


class CompilationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    assistant_content: str
    summary: str
    strategy: StrategySpec | None = None
    model_provider: str | None = None
    model_name: str | None = None
    warning: str | None = None


def strategy_json_schema() -> dict[str, Any]:
    return StrategySpec.model_json_schema()
