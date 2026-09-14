# coding: utf-8
import unittest
from decimal import Decimal

from curs.domain.models import (
    InstrumentId,
    OrderIntent,
    OrderType,
    PositionSnapshot,
    Side,
)
from curs.trading_agent.risk import RiskContext, RiskGate


class TestRiskGate(unittest.TestCase):
    def test_t_plus_one_available_quantity_blocks_sell(self):
        instrument = InstrumentId.parse('CN_EQUITY:XSHG:600000')
        position = PositionSnapshot(
            instrument=instrument,
            quantity=Decimal('200'),
            available_quantity=Decimal('100'),
            average_price=Decimal('10'),
            last_price=Decimal('11'),
        )
        intent = OrderIntent(
            agent_id='agent',
            signal_id='signal',
            account_id='account',
            instrument=instrument,
            side=Side.SELL,
            order_type=OrderType.LIMIT,
            quantity=Decimal('200'),
            reference_price=Decimal('11'),
            limit_price=Decimal('11'),
        )
        context = RiskContext(
            total_equity=Decimal('100000'),
            available_cash=Decimal('10000'),
            position=position,
            trading_enabled=True,
        )

        result = RiskGate().evaluate(intent, context)

        self.assertFalse(result.approved)
        self.assertIn('INSUFFICIENT_AVAILABLE_POSITION', result.reason_codes)

    def test_kill_switch_always_blocks_order(self):
        instrument = InstrumentId.parse('CRYPTO:BINANCE:BTC-USDT')
        intent = OrderIntent(
            agent_id='agent',
            signal_id='signal',
            account_id='account',
            instrument=instrument,
            side=Side.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal('0.01'),
            reference_price=Decimal('50000'),
        )
        context = RiskContext(
            total_equity=Decimal('100000'),
            available_cash=Decimal('100000'),
            trading_enabled=True,
            kill_switch=True,
        )

        result = RiskGate().evaluate(intent, context)

        self.assertFalse(result.approved)
        self.assertIn('KILL_SWITCH_ACTIVE', result.reason_codes)


if __name__ == '__main__':
    unittest.main()
