# coding: utf-8
"""Health, status and real-time system event endpoints."""

import asyncio
from datetime import datetime
from typing import Annotated, AsyncIterator

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from trading_v2.api.dependencies import get_event_stream, get_runtime_state, get_settings
from trading_v2.config.settings import AppSettings
from trading_v2.domain.base import utc_now
from trading_v2.events import InMemoryEventStream
from trading_v2.runtime import RuntimeSnapshot, RuntimeStateStore

router = APIRouter(tags=["system"])


class LivenessResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: str = "alive"
    service: str
    version: str
    timestamp: datetime = Field(default_factory=utc_now)


class ReadinessResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: str
    ready: bool
    phase: str
    timestamp: datetime = Field(default_factory=utc_now)


@router.get("/health/live", response_model=LivenessResponse)
async def liveness(
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> LivenessResponse:
    return LivenessResponse(
        service=settings.service_name,
        version=settings.service_version,
    )


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness(
    runtime_state: Annotated[RuntimeStateStore, Depends(get_runtime_state)],
) -> ReadinessResponse:
    snapshot = await runtime_state.snapshot()
    return ReadinessResponse(
        status="ready" if snapshot.ready else "not_ready",
        ready=snapshot.ready,
        phase=snapshot.phase.value,
    )


@router.get("/status", response_model=RuntimeSnapshot)
async def status(
    runtime_state: Annotated[RuntimeStateStore, Depends(get_runtime_state)],
) -> RuntimeSnapshot:
    return await runtime_state.snapshot()


@router.get("/events")
async def events(
    request: Request,
    event_stream: Annotated[InMemoryEventStream, Depends(get_event_stream)],
    replay: int = Query(default=20, ge=0, le=500),
) -> StreamingResponse:
    async def generate() -> AsyncIterator[str]:
        subscription = await event_stream.subscribe(replay=replay)
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(subscription.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield (
                    f"id: {event.sequence}\n"
                    f"event: {event.topic}\n"
                    f"data: {event.model_dump_json()}\n\n"
                )
        finally:
            await subscription.close()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
