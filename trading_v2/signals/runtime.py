# coding: utf-8
"""Background scanner that evaluates running sessions on closed bars."""

import asyncio
import logging

from trading_v2.agent.models import StrategySpec
from trading_v2.domain.enums import AssetClass
from trading_v2.domain.market import InstrumentId
from trading_v2.domain.signal import Signal
from trading_v2.events import InMemoryEventStream
from trading_v2.market.provider import MarketDataProvider
from trading_v2.sessions.service import TradingSessionService
from trading_v2.signals.evaluator import StrategyEvaluator
from trading_v2.signals.repository import SignalRepository

logger = logging.getLogger(__name__)


class SignalRuntime:
    def __init__(
        self,
        sessions: TradingSessionService,
        market: MarketDataProvider,
        repository: SignalRepository,
        events: InMemoryEventStream,
        poll_interval_seconds: float = 5,
        bar_limit: int = 200,
    ) -> None:
        self.sessions = sessions
        self.market = market
        self.repository = repository
        self.events = events
        self.poll_interval_seconds = poll_interval_seconds
        self.bar_limit = bar_limit
        self.evaluator = StrategyEvaluator()
        self._task: asyncio.Task | None = None
        self._scan_lock = asyncio.Lock()

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="closed-bar-signal-runtime")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def evaluate_once(self, session_id: str | None = None) -> list[Signal]:
        async with self._scan_lock:
            targets = await self.sessions.runtime_targets(session_id)
            created: list[Signal] = []
            for session, version, strategy in targets:
                signal = await self._evaluate(session.id, version, strategy)
                if signal is not None:
                    created.append(signal)
            return created

    async def _evaluate(self, session_id: str, version: int, strategy: StrategySpec) -> Signal | None:
        instrument = _parse_instrument(strategy.instrument)
        bars = await self.market.get_bars(instrument, strategy.timeframe, self.bar_limit)
        signal = self.evaluator.evaluate(session_id, version, strategy, bars)
        if signal is None:
            return None
        saved = await asyncio.to_thread(self.repository.save, signal)
        if not saved:
            return None
        await self.events.publish("signal", {
            "session_id": session_id, "signal_id": str(signal.id),
            "strategy_version": version, "side": signal.side.value,
            "bar_time": signal.bar_time.isoformat(), "reason": signal.reason,
        })
        return signal

    async def _run(self) -> None:
        while True:
            try:
                await self.evaluate_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("closed-bar signal scan failed")
            await asyncio.sleep(self.poll_interval_seconds)


def _parse_instrument(value: str) -> InstrumentId:
    asset_class, venue, symbol = value.split(":")
    return InstrumentId(asset_class=AssetClass(asset_class), venue=venue, symbol=symbol)
