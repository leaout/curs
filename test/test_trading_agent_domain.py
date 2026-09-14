# coding: utf-8
import unittest
from decimal import Decimal

from curs.domain.models import InstrumentId
from curs.markets.profiles import MarketRegistry
from curs.trading_agent.strategy_generator import (
    StrategyGenerator,
    StrategyNeedsClarification,
)
from curs.trading_agent.strategy_spec import StrategySpec


class TestInstrumentAndMarkets(unittest.TestCase):
    def test_instrument_round_trip(self):
        instrument = InstrumentId.parse('crypto:binance:btc-usdt')

        self.assertEqual(instrument.asset_class, 'CRYPTO')
        self.assertEqual(str(instrument), 'CRYPTO:BINANCE:BTC-USDT')

    def test_market_quantity_normalization(self):
        registry = MarketRegistry.defaults()
        cn = registry.get(InstrumentId.parse('CN_EQUITY:XSHG:600000'))
        crypto = registry.get(InstrumentId.parse('CRYPTO:BINANCE:BTC-USDT'))

        self.assertEqual(cn.normalize_quantity(Decimal('299')), Decimal('200'))
        self.assertEqual(
            crypto.normalize_quantity(Decimal('0.123456789')),
            Decimal('0.123456'),
        )


class TestStrategySpec(unittest.TestCase):
    def test_parse_safe_strategy_spec(self):
        spec = StrategySpec.from_dict({
            'id': 'btc-breakout',
            'name': 'BTC breakout',
            'market': {
                'asset_classes': ['crypto'],
                'venues': ['binance'],
                'instruments': ['CRYPTO:BINANCE:BTC-USDT'],
            },
            'timeframe': '5m',
            'trigger': {
                'all': [
                    {'field': 'volume_ratio_20', 'operator': 'gte', 'value': 2},
                ],
            },
        })

        self.assertEqual(spec.asset_classes, ('CRYPTO',))
        self.assertEqual(spec.trigger_all[0].operator, 'gte')

    def test_reject_unsafe_operator(self):
        with self.assertRaises(ValueError):
            StrategySpec.from_dict({
                'id': 'unsafe',
                'trigger': {
                    'all': [
                        {'field': 'close', 'operator': 'eval', 'value': 'x'},
                    ],
                },
            })

    def test_generator_returns_clarification(self):
        generator = StrategyGenerator(lambda _: {
            'needs_clarification': True,
            'questions': ['使用哪个市场？'],
        })

        with self.assertRaises(StrategyNeedsClarification) as context:
            generator.generate('帮我赚钱')
        self.assertEqual(context.exception.questions, ('使用哪个市场？',))


if __name__ == '__main__':
    unittest.main()
