# coding: utf-8
"""Application service for persistent strategy conversations."""

import asyncio
import re
from datetime import datetime, timezone
from uuid import uuid4

from trading_v2.agent.compiler import StrategyCompiler
from trading_v2.domain.enums import AssetClass
from trading_v2.events import InMemoryEventStream
from trading_v2.sessions.models import (
    ChatMessage,
    CreateSession,
    SessionSnapshot,
    SessionStatus,
    TradingSession,
)
from trading_v2.sessions.repository import SessionRepository


class TradingSessionService:
    def __init__(
        self,
        repository: SessionRepository,
        compiler: StrategyCompiler,
        events: InMemoryEventStream,
    ) -> None:
        self.repository = repository
        self.compiler = compiler
        self.events = events

    async def initialize(self) -> None:
        await asyncio.to_thread(self.repository.initialize)

    async def list_sessions(self) -> list[TradingSession]:
        return await asyncio.to_thread(self.repository.list_sessions)

    async def get_snapshot(self, session_id: str) -> SessionSnapshot | None:
        return await asyncio.to_thread(self.repository.get_snapshot, session_id)

    async def create_session(self, command: CreateSession) -> SessionSnapshot:
        symbol, venue, timeframe = _infer_market(command)
        compilation = await self.compiler.compile(command.message)
        asset_class = command.asset_class
        name = command.name or _short_name(command.message)
        if compilation.strategy is not None:
            raw_asset, venue, symbol = compilation.strategy.instrument.split(":")
            asset_class = AssetClass(raw_asset)
            timeframe = compilation.strategy.timeframe
            name = compilation.strategy.name
        now = datetime.now(timezone.utc)
        session = TradingSession(
            id=str(uuid4()), name=name, symbol=symbol, venue=venue,
            asset_class=asset_class, timeframe=timeframe, status=SessionStatus.DRAFT,
            mode=command.mode, prompt_version=1, created_at=now, updated_at=now,
        )
        snapshot = await asyncio.to_thread(
            self.repository.create_session, session, command.message, compilation
        )
        await self.events.publish("session.created", {
            "session_id": session.id, "prompt_version": 1,
            "strategy_valid": compilation.strategy is not None,
        })
        return snapshot

    async def send_message(self, session_id: str, content: str) -> ChatMessage | None:
        previous = await asyncio.to_thread(self.repository.latest_strategy, session_id)
        compilation = await self.compiler.compile(content, previous)
        message = await asyncio.to_thread(
            self.repository.append_turn, session_id, content, compilation
        )
        if message is not None:
            await self.events.publish("strategy.drafted", {
                "session_id": session_id,
                "prompt_version": message.version,
                "strategy_valid": compilation.strategy is not None,
                "warning": compilation.warning,
            })
        return message

    async def set_paused(self, session_id: str, paused: bool) -> TradingSession | None:
        if paused:
            status = SessionStatus.PAUSED
        else:
            strategy = await asyncio.to_thread(self.repository.latest_strategy, session_id)
            status = SessionStatus.RUNNING if strategy else SessionStatus.DRAFT
        session = await asyncio.to_thread(self.repository.set_status, session_id, status)
        if session is not None:
            await self.events.publish("session.updated", {
                "session_id": session_id, "status": session.status.value,
            })
        return session

    async def close(self) -> None:
        await self.compiler.close()
        self.repository.database.close()


def _infer_market(command: CreateSession) -> tuple[str, str, str]:
    symbol = (command.symbol or "").strip().upper()
    match = re.search(r"(?<!\d)(\d{6})(?!\d)", command.message)
    if not symbol and match:
        symbol = match.group(1)
    symbol = symbol or "600519"
    venue = (command.venue or "").strip().upper()
    if not venue:
        venue = "XSHG" if symbol.startswith(("5", "6", "9")) else "XSHE"
    timeframe = command.timeframe
    timeframe_match = re.search(r"(1|5|15|30|60)\s*分钟", command.message)
    if timeframe_match:
        timeframe = "1h" if timeframe_match.group(1) == "60" else f"{timeframe_match.group(1)}m"
    return symbol, venue, timeframe


def _short_name(message: str) -> str:
    compact = " ".join(message.split())
    return compact if len(compact) <= 24 else f"{compact[:24]}…"
