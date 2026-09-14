# coding: utf-8
"""将标准成交 Tick 聚合为多个周期的闭合 K 线。"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Iterable, List, Tuple

from curs.domain.models import Bar, TradeTick


@dataclass
class _WorkingBar:
    opened_at: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


class MultiTimeframeBarAggregator:
    def __init__(self, timeframes: Iterable[int] = (1, 5, 15)):
        values = tuple(sorted(set(int(value) for value in timeframes)))
        if not values or any(value <= 0 for value in values):
            raise ValueError('timeframes must contain positive minute values')
        self._timeframes = values
        self._working: Dict[Tuple[str, int], _WorkingBar] = {}
        self._last_timestamp: Dict[str, datetime] = {}

    def update(self, tick: TradeTick) -> List[Bar]:
        instrument_key = str(tick.instrument)
        previous_timestamp = self._last_timestamp.get(instrument_key)
        if previous_timestamp is not None and tick.timestamp <= previous_timestamp:
            return []
        self._last_timestamp[instrument_key] = tick.timestamp
        closed = []
        for minutes in self._timeframes:
            opened_at = _bucket_start(tick.timestamp, minutes)
            key = (instrument_key, minutes)
            working = self._working.get(key)
            if working is not None and opened_at > working.opened_at:
                closed.append(Bar(
                    instrument=tick.instrument,
                    timeframe=f'{minutes}m',
                    opened_at=working.opened_at,
                    closed_at=working.opened_at + timedelta(minutes=minutes),
                    open=working.open,
                    high=working.high,
                    low=working.low,
                    close=working.close,
                    volume=working.volume,
                ))
                working = None

            if working is None:
                self._working[key] = _WorkingBar(
                    opened_at=opened_at,
                    open=tick.price,
                    high=tick.price,
                    low=tick.price,
                    close=tick.price,
                    volume=tick.volume,
                )
            else:
                working.high = max(working.high, tick.price)
                working.low = min(working.low, tick.price)
                working.close = tick.price
                working.volume += tick.volume
        return closed


def _bucket_start(timestamp: datetime, minutes: int) -> datetime:
    minute = timestamp.minute - (timestamp.minute % minutes)
    return timestamp.replace(minute=minute, second=0, microsecond=0)
