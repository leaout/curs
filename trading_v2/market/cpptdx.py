# coding: utf-8
"""cpptdx HTTP 行情服务适配器。"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from time import perf_counter
from typing import Any, Awaitable, Callable, Dict, Optional, Sequence
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import aiohttp

from trading_v2.domain.market import (
    AssetClass,
    Bar,
    InstrumentId,
    MarketSnapshot,
)
from trading_v2.market.provider import MarketDataHealth


JsonRequest = Callable[[str, Dict[str, Any]], Awaitable[Any]]

_MARKETS = {'XSHE': 0, 'XSHG': 1}
_TIMEFRAMES = {
    '1m': (8, timedelta(minutes=1)),
    '5m': (0, timedelta(minutes=5)),
    '15m': (1, timedelta(minutes=15)),
    '30m': (2, timedelta(minutes=30)),
    '1h': (3, timedelta(hours=1)),
    '1d': (4, timedelta(days=1)),
}
_SHANGHAI = ZoneInfo('Asia/Shanghai')


class CppTdxError(RuntimeError):
    """cpptdx 请求或响应错误。"""


class CppTdxMarketDataProvider:
    """通过 cpptdx 的 HTTP API 提供 A 股快照和 K 线。

    cpptdx 当前不推送逐笔数据，所以 ``stream_snapshots`` 使用有界频率轮询。
    """

    def __init__(
        self,
        base_url: str = 'http://127.0.0.1:8022',
        timeout_seconds: float = 3,
        snapshot_interval_ms: int = 1000,
        max_batch_size: int = 50,
        stale_after_seconds: int = 5,
        request: Optional[JsonRequest] = None,
    ):
        if timeout_seconds <= 0:
            raise ValueError('timeout_seconds must be positive')
        if snapshot_interval_ms < 200:
            raise ValueError('snapshot_interval_ms must be at least 200')
        if not 1 <= max_batch_size <= 80:
            raise ValueError('max_batch_size must be between 1 and 80')
        if stale_after_seconds <= 0:
            raise ValueError('stale_after_seconds must be positive')
        self.base_url = base_url.rstrip('/') + '/'
        self.timeout_seconds = timeout_seconds
        self.snapshot_interval_ms = snapshot_interval_ms
        self.max_batch_size = max_batch_size
        self.stale_after_seconds = stale_after_seconds
        self._request = request
        self._session: Optional[aiohttp.ClientSession] = None

    async def health(self) -> MarketDataHealth:
        started = perf_counter()
        try:
            payload = await self._get('health', {})
            healthy = isinstance(payload, dict) and payload.get('status') == 'ok'
            return MarketDataHealth(
                healthy=healthy,
                source='cpptdx',
                latency_ms=round((perf_counter() - started) * 1000, 2),
                detail='HTTP service is reachable; upstream status is not exposed'
                if healthy else 'unexpected health response',
            )
        except Exception as exc:
            return MarketDataHealth(
                healthy=False,
                source='cpptdx',
                latency_ms=round((perf_counter() - started) * 1000, 2),
                detail=str(exc),
            )

    async def get_snapshots(
        self,
        instruments: Sequence[InstrumentId],
    ) -> list[MarketSnapshot]:
        if not instruments:
            return []
        snapshots = []
        for offset in range(0, len(instruments), self.max_batch_size):
            batch = instruments[offset:offset + self.max_batch_size]
            lookup = {item.symbol: item for item in batch}
            stocks = [
                {'code': item.symbol, 'market': str(_market_code(item))}
                for item in batch
            ]
            payload = await self._get(
                'api/snapshots', {'stocks': json.dumps(stocks, separators=(',', ':'))}
            )
            if not isinstance(payload, list):
                raise CppTdxError('snapshots response must be a JSON array')
            for raw in payload:
                symbol = str(raw.get('code', '')).strip()
                instrument = lookup.get(symbol)
                if instrument is None:
                    continue
                snapshots.append(self._snapshot(instrument, raw))
        return snapshots

    async def get_bars(
        self,
        instrument: InstrumentId,
        timeframe: str,
        limit: int,
    ) -> list[Bar]:
        _market_code(instrument)
        if timeframe not in _TIMEFRAMES:
            raise ValueError(f'unsupported cpptdx timeframe: {timeframe}')
        if not 1 <= limit <= 800:
            raise ValueError('limit must be between 1 and 800')
        category, duration = _TIMEFRAMES[timeframe]
        payload = await self._get('api/klines', {
            'cat': category,
            'market': _market_code(instrument),
            'code': instrument.symbol,
            'start': 0,
            'count': limit,
        })
        if not isinstance(payload, list):
            raise CppTdxError('klines response must be a JSON array')
        now = datetime.now(timezone.utc)
        bars = []
        for raw in payload:
            opened_at = _parse_kline_time(raw.get('datetime'))
            closed_at = opened_at + duration
            bars.append(Bar(
                instrument=instrument,
                timeframe=timeframe,
                open_time=opened_at,
                close_time=closed_at,
                open=_decimal(raw, 'open'),
                high=_decimal(raw, 'high'),
                low=_decimal(raw, 'low'),
                close=_decimal(raw, 'close'),
                volume=_decimal(raw, 'vol', '0'),
                turnover=_decimal(raw, 'amount', '0'),
                source='cpptdx',
                is_closed=now >= closed_at,
                received_at=now,
            ))
        return sorted(bars, key=lambda item: item.open_time)

    async def stream_snapshots(self, instruments):
        while True:
            for snapshot in await self.get_snapshots(instruments):
                yield snapshot
            await asyncio.sleep(self.snapshot_interval_ms / 1000)

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def __aenter__(self) -> 'CppTdxMarketDataProvider':
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        await self.close()

    async def _get(self, path: str, params: Dict[str, Any]) -> Any:
        url = urljoin(self.base_url, path)
        if self._request is not None:
            return await self._request(url, params)
        if self._session is None:
            timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
            self._session = aiohttp.ClientSession(timeout=timeout)
        try:
            async with self._session.get(url, params=params) as response:
                response.raise_for_status()
                return await response.json()
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
            raise CppTdxError(f'cpptdx request failed: {exc}') from exc

    def _snapshot(
        self,
        instrument: InstrumentId,
        raw: Dict[str, Any],
    ) -> MarketSnapshot:
        received_at = datetime.now(timezone.utc)
        market_time = _parse_snapshot_time(raw.get('datetime'))
        age = (received_at - market_time).total_seconds()
        return MarketSnapshot(
            instrument=instrument,
            last=_decimal(raw, 'price'),
            open=_positive_decimal_or_none(raw.get('open')),
            high=_positive_decimal_or_none(raw.get('high')),
            low=_positive_decimal_or_none(raw.get('low')),
            prev_close=_positive_decimal(raw.get('last_close'), 'last_close'),
            bid=_positive_decimal_or_none(raw.get('bid1')),
            ask=_positive_decimal_or_none(raw.get('ask1')),
            volume=_decimal(raw, 'vol', '0'),
            turnover=_decimal(raw, 'amount', '0'),
            market_time=market_time,
            received_at=received_at,
            source='cpptdx',
            stale=age > self.stale_after_seconds or age < -60,
        )


def _market_code(instrument: InstrumentId) -> int:
    if instrument.asset_class != AssetClass.CN_EQUITY:
        raise ValueError('cpptdx only supports CN_EQUITY')
    try:
        return _MARKETS[instrument.venue]
    except KeyError as exc:
        raise ValueError(f'cpptdx does not support venue: {instrument.venue}') from exc


def _decimal(raw: Dict[str, Any], key: str, default: str = None) -> Decimal:
    value = raw.get(key, default)
    if value is None:
        raise CppTdxError(f'missing numeric field: {key}')
    try:
        return Decimal(str(value))
    except Exception as exc:
        raise CppTdxError(f'invalid numeric field {key}: {value!r}') from exc


def _positive_decimal(value: Any, field: str) -> Decimal:
    parsed = _optional_decimal(value)
    if parsed is None or parsed <= 0:
        raise CppTdxError(f'invalid positive numeric field {field}: {value!r}')
    return parsed


def _positive_decimal_or_none(value: Any) -> Optional[Decimal]:
    parsed = _optional_decimal(value)
    return parsed if parsed is not None and parsed > 0 else None


def _optional_decimal(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception as exc:
        raise CppTdxError(f'invalid numeric value: {value!r}') from exc


def _parse_snapshot_time(value: Any) -> datetime:
    try:
        text = f'{int(value):09d}'
        hour, minute, second = int(text[:2]), int(text[2:4]), int(text[4:6])
        local_now = datetime.now(_SHANGHAI)
        local_value = local_now.replace(
            hour=hour, minute=minute, second=second, microsecond=0
        )
        return local_value.astimezone(timezone.utc)
    except (TypeError, ValueError) as exc:
        raise CppTdxError(f'invalid snapshot datetime: {value!r}') from exc


def _parse_kline_time(value: Any) -> datetime:
    try:
        text = str(int(value))
        pattern = '%Y%m%d%H%M' if len(text) > 8 else '%Y%m%d'
        return datetime.strptime(text, pattern).replace(
            tzinfo=_SHANGHAI
        ).astimezone(timezone.utc)
    except (TypeError, ValueError) as exc:
        raise CppTdxError(f'invalid kline datetime: {value!r}') from exc
