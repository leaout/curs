# coding: utf-8
"""Typed FastAPI dependencies backed by application state."""

from fastapi import Request

from trading_v2.config.settings import AppSettings
from trading_v2.events import InMemoryEventStream
from trading_v2.market.provider import MarketDataProvider
from trading_v2.runtime import RuntimeStateStore


def get_settings(request: Request) -> AppSettings:
    return request.app.state.settings


def get_event_stream(request: Request) -> InMemoryEventStream:
    return request.app.state.event_stream


def get_runtime_state(request: Request) -> RuntimeStateStore:
    return request.app.state.runtime_state


def get_market_data(request: Request) -> MarketDataProvider:
    return request.app.state.market_data
