# coding: utf-8
"""Provider-neutral market-data query endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from trading_v2.api.dependencies import get_market_data
from trading_v2.domain.enums import AssetClass
from trading_v2.domain.market import Bar, InstrumentId, MarketSnapshot
from trading_v2.market.cpptdx import CppTdxError
from trading_v2.market.provider import MarketDataHealth, MarketDataProvider

router = APIRouter(prefix="/market", tags=["market"])


class SnapshotRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    instruments: list[str] = Field(min_length=1, max_length=80)


def parse_instrument(value: str) -> InstrumentId:
    parts = value.strip().split(":")
    if len(parts) != 3:
        raise ValueError("instrument must be asset_class:venue:symbol")
    asset_class, venue, symbol = parts
    try:
        return InstrumentId(
            asset_class=AssetClass(asset_class.lower()),
            venue=venue,
            symbol=symbol,
        )
    except (ValueError, TypeError) as exc:
        raise ValueError(f"invalid instrument: {value}") from exc


def provider_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=502, detail=f"market data unavailable: {exc}")


@router.get("/status", response_model=MarketDataHealth)
async def market_status(
    market_data: Annotated[MarketDataProvider, Depends(get_market_data)],
) -> MarketDataHealth:
    return await market_data.health()


@router.get("/bars", response_model=list[Bar])
async def market_bars(
    market_data: Annotated[MarketDataProvider, Depends(get_market_data)],
    instrument: str = Query(description="asset_class:venue:symbol"),
    timeframe: str = Query(default="5m"),
    limit: int = Query(default=200, ge=1, le=800),
) -> list[Bar]:
    try:
        return await market_data.get_bars(
            parse_instrument(instrument),
            timeframe=timeframe,
            limit=limit,
        )
    except (CppTdxError, ValueError) as exc:
        raise provider_error(exc) from exc


@router.post("/snapshots", response_model=list[MarketSnapshot])
async def market_snapshots(
    request: SnapshotRequest,
    market_data: Annotated[MarketDataProvider, Depends(get_market_data)],
) -> list[MarketSnapshot]:
    try:
        instruments = [parse_instrument(value) for value in request.instruments]
        return await market_data.get_snapshots(instruments)
    except (CppTdxError, ValueError) as exc:
        raise provider_error(exc) from exc
