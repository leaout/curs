# coding: utf-8
"""行情源必须实现的最小接口。"""

from dataclasses import dataclass
from typing import AsyncIterator, Protocol, Sequence

from trading_v2.domain.market import Bar, InstrumentId, MarketSnapshot


@dataclass(frozen=True)
class MarketDataHealth:
    healthy: bool
    source: str
    latency_ms: float = 0
    detail: str = ''


class MarketDataProvider(Protocol):
    async def health(self) -> MarketDataHealth:
        ...

    async def get_snapshots(
        self,
        instruments: Sequence[InstrumentId],
    ) -> list[MarketSnapshot]:
        ...

    async def get_bars(
        self,
        instrument: InstrumentId,
        timeframe: str,
        limit: int,
    ) -> list[Bar]:
        ...

    async def stream_snapshots(
        self,
        instruments: Sequence[InstrumentId],
    ) -> AsyncIterator[MarketSnapshot]:
        ...

    async def close(self) -> None:
        ...
