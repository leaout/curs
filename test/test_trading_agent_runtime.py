# coding: utf-8
import time
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from curs.domain.models import Action, Bar, Decision, InstrumentId
from curs.trading_agent.ai_decision import DecisionProvider
from curs.trading_agent.execution import ExecutionEngine, ExecutionResult
from curs.trading_agent.journal import MemoryTradingJournal
from curs.trading_agent.risk import RiskContext
from curs.trading_agent.runtime import TradingAgentRuntime
from curs.trading_agent.strategy_spec import StrategySpec


class BuyDecisionProvider:
    def decide(self, context):
        return Decision(
            signal_id=context['signal']['signal_id'],
            action=Action.BUY,
            confidence=Decimal('0.8'),
            position_pct=Decimal('0.1'),
            limit_price=Decimal(context['signal']['price']),
        )


class SlowDecisionProvider:
    def decide(self, context):
        time.sleep(0.05)
        return BuyDecisionProvider().decide(context)


class CapturingBroker:
    def __init__(self):
        self.intents = []

    def place_order(self, intent):
        self.intents.append(intent)
        return ExecutionResult(True, broker_order_id='order-1')


def make_spec():
    return StrategySpec.from_dict({
        'id': 'cn-minute-agent',
        'name': 'CN minute agent',
        'market': {
            'asset_classes': ['cn_equity'],
            'venues': ['xshg'],
            'instruments': ['CN_EQUITY:XSHG:600000'],
        },
        'timeframe': '5m',
        'trigger': {
            'all': [{'field': 'close', 'operator': 'gte', 'value': 10}],
        },
        'ai_decision': {'cooldown_seconds': 600},
        'position': {'allocation_pct': 0.1, 'max_position_pct': 0.15},
    })


def make_bar(offset_minutes=0):
    closed_at = datetime.now(timezone.utc) + timedelta(minutes=offset_minutes)
    return Bar(
        instrument=InstrumentId.parse('CN_EQUITY:XSHG:600000'),
        timeframe='5m',
        opened_at=closed_at - timedelta(minutes=5),
        closed_at=closed_at,
        open=Decimal('10'),
        high=Decimal('11.2'),
        low=Decimal('9.9'),
        close=Decimal('11'),
        volume=Decimal('100000'),
    )


class TestTradingAgentRuntime(unittest.TestCase):
    def setUp(self):
        self.broker = CapturingBroker()
        self.journal = MemoryTradingJournal()

    @staticmethod
    def risk_context(trading_enabled=True):
        return RiskContext(
            total_equity=Decimal('100000'),
            available_cash=Decimal('100000'),
            trading_enabled=trading_enabled,
        )

    def make_runtime(self, trading_enabled=True):
        return TradingAgentRuntime(
            specs=[make_spec()],
            decision_provider=BuyDecisionProvider(),
            risk_context_provider=lambda _: self.risk_context(trading_enabled),
            execution_engine=ExecutionEngine(self.broker),
            account_id='test-account',
            journal=self.journal,
        )

    def test_signal_to_ai_risk_and_execution(self):
        outcomes = self.make_runtime().on_bar(make_bar())

        self.assertEqual(outcomes[0].status, 'ORDER_SUBMITTED')
        self.assertEqual(len(self.broker.intents), 1)
        self.assertEqual(self.broker.intents[0].quantity, Decimal('900'))
        self.assertEqual(
            [event['event_type'] for event in self.journal.events],
            ['CANDIDATE_SIGNAL', 'AI_DECISION', 'RISK_DECISION', 'EXECUTION_RESULT'],
        )

    def test_live_trading_disabled_blocks_order(self):
        outcomes = self.make_runtime(trading_enabled=False).on_bar(make_bar())

        self.assertEqual(outcomes[0].status, 'RISK_REJECTED')
        self.assertIn(
            'LIVE_TRADING_DISABLED',
            outcomes[0].risk_result.reason_codes,
        )
        self.assertEqual(self.broker.intents, [])

    def test_cooldown_suppresses_repeated_signal(self):
        runtime = self.make_runtime()
        runtime.on_bar(make_bar())
        outcomes = runtime.on_bar(make_bar(offset_minutes=5))

        self.assertEqual(outcomes[0].status, 'DEDUPLICATED')
        self.assertEqual(len(self.broker.intents), 1)

    def test_ai_timeout_defaults_to_no_order(self):
        spec = make_spec()
        spec = replace(
            spec,
            ai_decision=replace(spec.ai_decision, timeout_seconds=0.01),
        )
        runtime = TradingAgentRuntime(
            specs=[spec],
            decision_provider=SlowDecisionProvider(),
            risk_context_provider=lambda _: self.risk_context(True),
            execution_engine=ExecutionEngine(self.broker),
            account_id='test-account',
            journal=self.journal,
        )

        outcomes = runtime.on_bar(make_bar())

        self.assertEqual(outcomes[0].status, 'DECISION_ERROR')
        self.assertEqual(self.broker.intents, [])


if __name__ == '__main__':
    unittest.main()
