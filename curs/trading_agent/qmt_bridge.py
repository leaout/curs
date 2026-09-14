# coding: utf-8
"""将当前 Curs 的 QMT Tick 事件桥接到 Trading Agent。"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

from curs.domain.models import InstrumentId, TradeTick
from curs.events import EVENT
from curs.trading_agent.bar_aggregator import MultiTimeframeBarAggregator
from curs.trading_agent.runtime import TradingAgentRuntime

logger = logging.getLogger(__name__)


class QmtTickNormalizer:
    """将 xtquant 快照转换为增量成交 Tick。"""

    def __init__(self):
        self._last_volume: Dict[str, Decimal] = {}

    def normalize(self, stock_code: str, raw: Dict[str, Any]) -> Optional[TradeTick]:
        price = Decimal(str(raw.get('lastPrice') or raw.get('last_price') or 0))
        timestamp_ms = int(raw.get('time') or 0)
        if price <= 0 or timestamp_ms <= 0:
            return None

        cumulative = Decimal(str(raw.get('volume') or 0))
        previous = self._last_volume.get(stock_code)
        volume = Decimal('0') if previous is None else max(Decimal('0'), cumulative - previous)
        self._last_volume[stock_code] = cumulative
        return TradeTick(
            instrument=_qmt_instrument(stock_code),
            timestamp=datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc),
            price=price,
            volume=volume,
        )


class QmtTradingAgentBridge:
    def __init__(self, event_bus, runtime: TradingAgentRuntime):
        self._event_bus = event_bus
        self._runtime = runtime
        self._normalizer = QmtTickNormalizer()
        self._aggregator = MultiTimeframeBarAggregator()
        self._started = False

    def start(self) -> None:
        if not self._started:
            self._event_bus.add_listener(EVENT.TICK, self._on_tick)
            self._started = True

    def stop(self) -> None:
        if self._started:
            self._event_bus.del_listener(EVENT.TICK, self._on_tick)
            self._started = False

    def _on_tick(self, event) -> None:
        try:
            for stock_code, raw in event.tick.items():
                tick = self._normalizer.normalize(stock_code, raw)
                if tick is None:
                    continue
                for bar in self._aggregator.update(tick):
                    self._runtime.on_bar(bar)
        except Exception:
            logger.exception('Trading Agent QMT tick bridge failed')


def _qmt_instrument(stock_code: str) -> InstrumentId:
    code, _, suffix = stock_code.upper().partition('.')
    venues = {'SH': 'XSHG', 'SZ': 'XSHE', 'BJ': 'XBSE'}
    try:
        venue = venues[suffix]
    except KeyError as exc:
        raise ValueError(f'unsupported QMT stock code: {stock_code}') from exc
    return InstrumentId('CN_EQUITY', venue, code)
