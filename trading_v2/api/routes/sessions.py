# coding: utf-8
"""Persistent strategy-session and conversation endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from trading_v2.api.dependencies import get_session_service
from trading_v2.sessions.models import (
    ChatMessage,
    CreateSession,
    SendMessage,
    SessionSnapshot,
    TradingSession,
)
from trading_v2.sessions.service import TradingSessionService

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
