# coding: utf-8
import unittest

from trading_v2.agent.compiler import StrategyCompiler
from trading_v2.events import InMemoryEventStream
from trading_v2.sessions.models import CreateSession
from trading_v2.sessions.repository import SessionRepository
from trading_v2.sessions.service import TradingSessionService
from trading_v2.storage.database import Database


class StubModelProvider:
    provider_name = "stub"
    model_name = "strategy-test"

    async def complete_json(self, system_prompt, user_prompt, schema):
        return {
            "name": "贵州茅台均线突破",
            "thesis": "收盘价上穿二十周期均线时建立观察信号",
            "instrument": "cn_equity:XSHG:600519",
            "timeframe": "5m",
            "entry_rules": [{
                "indicator": "close",
                "operator": "cross_above",
                "compare_to": "ma:20",
                "params": {},
            }],
            "exit_rules": [{
                "indicator": "close",
                "operator": "cross_below",
                "compare_to": "ma:20",
                "params": {},
            }],
            "risk": {
                "max_position_pct": 0.05,
                "stop_loss_pct": 0.03,
                "take_profit_pct": 0.08,
                "max_daily_loss_pct": 0.02,
            },
        }

    async def close(self):
        return None


class InvalidModelProvider(StubModelProvider):
    async def complete_json(self, system_prompt, user_prompt, schema):
        return {"name": "not enough fields"}


class TradingSessionServiceTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.database = Database("sqlite:///:memory:")
        self.events = InMemoryEventStream()
        self.service = TradingSessionService(
            SessionRepository(self.database),
            StrategyCompiler(StubModelProvider()),
            self.events,
        )
        await self.service.initialize()

    async def asyncTearDown(self) -> None:
        await self.service.close()
        await self.events.close()

    async def test_create_modify_pause_and_resume_session(self) -> None:
        created = await self.service.create_session(CreateSession(
            message="为 600519 创建 5 分钟均线突破策略",
        ))
        session_id = created.session.id

        self.assertEqual(created.session.name, "贵州茅台均线突破")
        self.assertEqual(created.session.prompt_version, 1)
        self.assertEqual(created.prompt_versions[0].strategy["timeframe"], "5m")

        response = await self.service.send_message(session_id, "止损调整为 3%")
        snapshot = await self.service.get_snapshot(session_id)
        paused = await self.service.set_paused(session_id, True)
        resumed = await self.service.set_paused(session_id, False)

        self.assertEqual(response.version, 2)
        self.assertEqual(len(snapshot.messages), 4)
        self.assertEqual(snapshot.prompt_versions[0].version, 2)
        self.assertEqual(paused.status.value, "paused")
        self.assertEqual(resumed.status.value, "running")

    async def test_invalid_model_output_stays_a_safe_draft(self) -> None:
        service = TradingSessionService(
            SessionRepository(Database("sqlite:///:memory:")),
            StrategyCompiler(InvalidModelProvider()),
            self.events,
        )
        await service.initialize()
        try:
            created = await service.create_session(CreateSession(message="做一个策略"))
            self.assertEqual(created.session.status.value, "draft")
            self.assertIsNone(created.prompt_versions[0].strategy)
            self.assertIsNotNone(created.prompt_versions[0].warning)
        finally:
            await service.close()


if __name__ == "__main__":
    unittest.main()
