# coding: utf-8
"""In-process runtime status exposed by the V2 control plane."""

import asyncio
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from trading_v2.config.settings import AppSettings
from trading_v2.domain.base import utc_now
from trading_v2.domain.enums import ConnectionState, RuntimePhase, TradingMode


class ComponentStatus(BaseModel):
    model_config = ConfigDict(frozen=True)

    state: ConnectionState = ConnectionState.NOT_CONFIGURED
    provider: str | None = None
    message: str | None = None
    updated_at: datetime = Field(default_factory=utc_now)


class RuntimeSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    service_name: str
    service_version: str
    environment: str
    phase: RuntimePhase
    ready: bool
    trading_mode: TradingMode
    started_at: datetime
    updated_at: datetime
    active_sessions: int = Field(default=0, ge=0)
    last_event_at: datetime | None = None
    components: dict[str, ComponentStatus]


class RuntimeStateStore:
    """Concurrency-safe mutable holder that emits immutable snapshots."""

    def __init__(self, settings: AppSettings) -> None:
        now = utc_now()
        self._service_name = settings.service_name
        self._service_version = settings.service_version
        self._environment = settings.environment
        self._phase = RuntimePhase.STARTING
        self._mode = settings.trading_mode
        self._started_at = now
        self._updated_at = now
        self._active_sessions = 0
        self._last_event_at: datetime | None = None
        self._components = {
            "market_data": ComponentStatus(),
            "broker": ComponentStatus(),
            "model": ComponentStatus(),
        }
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        async with self._lock:
            self._phase = RuntimePhase.RUNNING
            self._updated_at = utc_now()

    async def stop(self) -> None:
        async with self._lock:
            self._phase = RuntimePhase.STOPPED
            self._updated_at = utc_now()

    async def set_phase(self, phase: RuntimePhase) -> None:
        async with self._lock:
            self._phase = phase
            self._updated_at = utc_now()

    async def set_mode(self, mode: TradingMode) -> None:
        async with self._lock:
            self._mode = mode
            self._updated_at = utc_now()

    async def set_active_sessions(self, count: int) -> None:
        if count < 0:
            raise ValueError("active session count cannot be negative")
        async with self._lock:
            self._active_sessions = count
            self._updated_at = utc_now()

    async def set_component(
        self,
        name: str,
        state: ConnectionState,
        provider: str | None = None,
        message: str | None = None,
    ) -> None:
        if not name.strip():
            raise ValueError("component name cannot be empty")
        async with self._lock:
            self._components[name] = ComponentStatus(
                state=state,
                provider=provider,
                message=message,
            )
            self._updated_at = utc_now()

    async def mark_event(self, occurred_at: datetime | None = None) -> None:
        async with self._lock:
            self._last_event_at = occurred_at or utc_now()
            self._updated_at = utc_now()

    async def snapshot(self) -> RuntimeSnapshot:
        async with self._lock:
            phase = self._phase
            return RuntimeSnapshot(
                service_name=self._service_name,
                service_version=self._service_version,
                environment=self._environment,
                phase=phase,
                ready=phase in {RuntimePhase.RUNNING, RuntimePhase.DEGRADED},
                trading_mode=self._mode,
                started_at=self._started_at,
                updated_at=self._updated_at,
                active_sessions=self._active_sessions,
                last_event_at=self._last_event_at,
                components=dict(self._components),
            )
