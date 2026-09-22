# coding: utf-8
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from trading_v2.agent.models import StrategySpec
from trading_v2.domain.market import Bar, InstrumentId
from trading_v2.events import InMemoryEventStream
from trading_v2.sessions.repository import SessionRepository  # registers session tables
from trading_v2.signals.evaluator import StrategyEvaluator
from trading_v2.signals.repository import SignalRepository
from trading_v2.signals.runtime import SignalRuntime
from trading_v2.storage.database import Database


def make_strategy() -> StrategySpec:
    return StrategySpec.model_validate({
        "name": "收盘价突破",
        "thesis": "收盘价从下方向上突破十元时产生候选信号",
        "instrument": "cn_equity:XSHG:600519",
        "timeframe": "5m",
        "entry_rules": [{
            "indicator": "close",
            "operator": "cross_above",
            "value": 10,
            "params": {},
        }],
        "exit_rules": [],
        "risk": {"max_position_pct": 0.05, "max_daily_loss_pct": 0.02},
    })


def make_bars() -> list[Bar]:
    instrument = InstrumentId(asset_class="cn_equity", venue="XSHG", symbol="600519")
    opened = datetime(2026, 9, 22, 1, 30, tzinfo=timezone.utc)
    bars = []
    for index, close in enumerate((Decimal("9.80"), Decimal("10.20"))):
        start = opened + timedelta(minutes=5 * index)
        bars.append(Bar(
            instrument=instrument,
            timeframe="5m",
            open_time=start,
            close_time=start + timedelta(minutes=5),
            open=Decimal("9.90"),
            high=max(close, Decimal("10.30")),
            low=min(close, Decimal("9.70")),
            close=close,
            volume=Decimal("1000"),
            source="test",
        ))
    return bars


class StubSessions:
    def __init__(self, session_id: str, strategy: StrategySpec) -> None:
        self.session_id = session_id
        self.strategy = strategy

    async def runtime_targets(self, session_id=None):
        if session_id is not None and session_id != self.session_id:
            return []
        return [(SimpleNamespace(id=self.session_id), 1, self.strategy)]


class StubMarket:
    async def get_bars(self, instrument, timeframe, limit):
        return make_bars()[:limit]


class TradingV2SignalsTest(unittest.IsolatedAsyncioTestCase):
    def test_evaluator_uses_closed_bar_crossing(self) -> None:
        session_id = str(uuid4())
        signal = StrategyEvaluator().evaluate(session_id, 1, make_strategy(), make_bars())

        self.assertIsNotNone(signal)
        self.assertEqual(signal.side.value, "buy")
        self.assertEqual(signal.bar_time, make_bars()[-1].close_time)
        self.assertTrue(signal.indicators["rules"][0]["matched"])

    async def test_runtime_persists_and_deduplicates_candidate_signal(self) -> None:
        session_id = str(uuid4())
        database = Database("sqlite:///:memory:")
        repository = SignalRepository(database)
        events = InMemoryEventStream()
        database.create_schema()
        runtime = SignalRuntime(
            sessions=StubSessions(session_id, make_strategy()),
            market=StubMarket(),
            repository=repository,
            events=events,
        )
        try:
            first = await runtime.evaluate_once(session_id)
            second = await runtime.evaluate_once(session_id)
            stored = repository.list_for_session(session_id)

            self.assertEqual(len(first), 1)
            self.assertEqual(second, [])
            self.assertEqual(len(stored), 1)
            self.assertEqual(stored[0]["side"], "BUY")
            self.assertEqual(stored[0]["state"], "candidate")
        finally:
            database.close()
            await events.close()


if __name__ == "__main__":
    unittest.main()
