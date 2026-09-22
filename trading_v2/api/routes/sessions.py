# coding: utf-8
"""Persistent strategy-session and conversation endpoints."""

import asyncio
from typing import Annotated, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from trading_v2.api.dependencies import get_event_stream, get_session_service, get_signal_runtime
from trading_v2.domain.signal import Signal
from trading_v2.events import InMemoryEventStream
from trading_v2.sessions.models import (
    ChatMessage,
    CreateSession,
    SendMessage,
    SessionSnapshot,
    TradingSession,
)
from trading_v2.sessions.service import TradingSessionService
from trading_v2.signals.runtime import SignalRuntime

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[TradingSession])
async def list_sessions(
    service: Annotated[TradingSessionService, Depends(get_session_service)],
) -> list[TradingSession]:
    return await service.list_sessions()


@router.post("", response_model=TradingSession, status_code=status.HTTP_201_CREATED)
async def create_session(
    command: CreateSession,
    service: Annotated[TradingSessionService, Depends(get_session_service)],
) -> TradingSession:
    snapshot = await service.create_session(command)
    return snapshot.session


@router.get("/{session_id}", response_model=SessionSnapshot)
async def get_session(
    session_id: str,
    service: Annotated[TradingSessionService, Depends(get_session_service)],
) -> SessionSnapshot:
    snapshot = await service.get_snapshot(session_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="strategy session not found")
    return snapshot


@router.post("/{session_id}/messages", response_model=ChatMessage)
async def send_message(
    session_id: str,
    command: SendMessage,
    service: Annotated[TradingSessionService, Depends(get_session_service)],
) -> ChatMessage:
    message = await service.send_message(session_id, command.content)
    if message is None:
        raise HTTPException(status_code=404, detail="strategy session not found")
    return message


@router.post("/{session_id}/pause", response_model=TradingSession)
async def pause_session(
    session_id: str,
    service: Annotated[TradingSessionService, Depends(get_session_service)],
) -> TradingSession:
    session = await service.set_paused(session_id, True)
    if session is None:
        raise HTTPException(status_code=404, detail="strategy session not found")
    return session


@router.post("/{session_id}/resume", response_model=TradingSession)
async def resume_session(
    session_id: str,
    service: Annotated[TradingSessionService, Depends(get_session_service)],
) -> TradingSession:
    session = await service.set_paused(session_id, False)
    if session is None:
        raise HTTPException(status_code=404, detail="strategy session not found")
    return session


@router.post("/{session_id}/evaluate", response_model=list[Signal])
async def evaluate_session(
    session_id: str,
    service: Annotated[TradingSessionService, Depends(get_session_service)],
    runtime: Annotated[SignalRuntime, Depends(get_signal_runtime)],
) -> list[Signal]:
    session = await service.get_snapshot(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="strategy session not found")
    return await runtime.evaluate_once(session_id)


@router.get("/{session_id}/events")
async def session_events(
    session_id: str,
    request: Request,
    service: Annotated[TradingSessionService, Depends(get_session_service)],
    stream: Annotated[InMemoryEventStream, Depends(get_event_stream)],
) -> StreamingResponse:
    if await service.get_snapshot(session_id) is None:
        raise HTTPException(status_code=404, detail="strategy session not found")

    async def generate() -> AsyncIterator[str]:
        subscription = await stream.subscribe(replay=50)
        try:
            while not await request.is_disconnected():
                try:
                    event = await asyncio.wait_for(subscription.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                if event.payload.get("session_id") != session_id:
                    continue
                event_name = event.topic.split(".", 1)[0]
                yield (
                    f"id: {event.sequence}\n"
                    f"event: {event_name}\n"
                    f"data: {event.model_dump_json()}\n\n"
                )
        finally:
            await subscription.close()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
