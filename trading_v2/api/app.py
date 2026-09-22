# coding: utf-8
"""FastAPI application factory for the standalone V2 service."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from trading_v2.api.routes.system import router as system_router
from trading_v2.api.routes.market import router as market_router
from trading_v2.api.routes.sessions import router as sessions_router
from trading_v2.agent.compiler import StrategyCompiler
from trading_v2.agent.providers import build_model_provider
from trading_v2.config.settings import AppSettings, get_settings
from trading_v2.domain.enums import ConnectionState
from trading_v2.events import InMemoryEventStream
from trading_v2.market import CppTdxMarketDataProvider, MarketDataProvider
from trading_v2.runtime import RuntimeStateStore
from trading_v2.sessions.repository import SessionRepository
from trading_v2.sessions.service import TradingSessionService
from trading_v2.storage.database import Database


def create_app(
    settings: AppSettings | None = None,
    event_stream: InMemoryEventStream | None = None,
    runtime_state: RuntimeStateStore | None = None,
    market_data: MarketDataProvider | None = None,
    session_service: TradingSessionService | None = None,
) -> FastAPI:
    """Build an isolated V2 application without importing the legacy runtime."""

    app_settings = settings or get_settings()
    stream = event_stream or InMemoryEventStream(
        history_size=app_settings.event_history_size,
        subscriber_queue_size=app_settings.event_subscriber_queue_size,
    )
    state = runtime_state or RuntimeStateStore(app_settings)
    market = market_data or CppTdxMarketDataProvider(
        base_url=app_settings.cpptdx_base_url,
        timeout_seconds=app_settings.cpptdx_timeout_seconds,
        snapshot_interval_ms=app_settings.cpptdx_snapshot_interval_ms,
    )
    sessions = session_service or TradingSessionService(
        repository=SessionRepository(Database(app_settings.database_url)),
        compiler=StrategyCompiler(build_model_provider(app_settings)),
        events=stream,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await sessions.initialize()
        await state.start()
        known_sessions = await sessions.list_sessions()
        await state.set_active_sessions(len(known_sessions))
        await state.set_component(
            "model",
            ConnectionState.CONNECTED if app_settings.model_enabled else ConnectionState.NOT_CONFIGURED,
            provider=app_settings.model_provider if app_settings.model_enabled else None,
            message=(
                f"{app_settings.model_name} configured"
                if app_settings.model_enabled
                else "model disabled; strategy changes remain drafts"
            ),
        )
        started = await stream.publish(
            "system.started",
            {
                "service": app_settings.service_name,
                "version": app_settings.service_version,
                "mode": app_settings.trading_mode.value,
            },
        )
        await state.mark_event(started.occurred_at)
        try:
            yield
        finally:
            await market.close()
            await sessions.close()
            await state.stop()
            stopped = await stream.publish(
                "system.stopped",
                {"service": app_settings.service_name},
            )
            await state.mark_event(stopped.occurred_at)
            await stream.close()

    app = FastAPI(
        title="Curs Trading V2",
        version=app_settings.service_version,
        debug=app_settings.debug,
        docs_url="/docs" if app_settings.docs_enabled else None,
        redoc_url="/redoc" if app_settings.docs_enabled else None,
        openapi_url="/openapi.json" if app_settings.docs_enabled else None,
        lifespan=lifespan,
    )
    app.state.settings = app_settings
    app.state.event_stream = stream
    app.state.runtime_state = state
    app.state.market_data = market
    app.state.session_service = sessions

    if app_settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=app_settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {
            "service": app_settings.service_name,
            "version": app_settings.service_version,
            "api": app_settings.api_prefix,
        }

    app.include_router(system_router, prefix=app_settings.api_prefix)
    app.include_router(market_router, prefix=app_settings.api_prefix)
    app.include_router(sessions_router, prefix=app_settings.api_prefix)
    return app
