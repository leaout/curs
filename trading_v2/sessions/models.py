# coding: utf-8
"""API-safe models for strategy sessions, messages and prompt versions."""

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from trading_v2.domain.enums import AssetClass, TradingMode


class SessionStatus(str, Enum):
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    ATTENTION = "attention"
    ARCHIVED = "archived"


class TradingSession(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    symbol: str
    venue: str
    asset_class: AssetClass
    timeframe: str
    status: SessionStatus
    mode: TradingMode
    pnl_percent: float = 0
    prompt_version: int = 0
    created_at: datetime
    updated_at: datetime


class ChatMessage(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    session_id: str
    role: Literal["user", "assistant", "system"]
    content: str
    created_at: datetime
    version: int | None = None
    status: Literal["complete", "failed"] = "complete"


class PromptVersion(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    session_id: str
    version: int
    prompt_text: str
    summary: str
    strategy: dict[str, Any] | None = None
    active: bool = True
    model_provider: str | None = None
    model_name: str | None = None
    warning: str | None = None
    created_at: datetime


class SessionSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    session: TradingSession
    messages: list[ChatMessage]
    prompt_versions: list[PromptVersion]
    candles: list[dict[str, Any]] = Field(default_factory=list)
    signals: list[dict[str, Any]] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)


class CreateSession(BaseModel):
    message: str = Field(min_length=1, max_length=4_000)
    name: str | None = Field(default=None, max_length=80)
    symbol: str | None = Field(default=None, max_length=40)
    venue: str | None = Field(default=None, max_length=20)
    asset_class: AssetClass = AssetClass.CN_EQUITY
    timeframe: str = "5m"
    mode: TradingMode = TradingMode.OBSERVE


class SendMessage(BaseModel):
    content: str = Field(min_length=1, max_length=4_000)
