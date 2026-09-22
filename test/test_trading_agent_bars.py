# coding: utf-8
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from curs.domain.models import InstrumentId, TradeTick
from curs.trading_agent.bar_aggregator import MultiTimeframeBarAggregator


class TestMultiTimeframeBarAggregator(unittest.TestCase):
    def test_closes_one_and_five_minute_bars(self):
        aggregator = MultiTimeframeBarAggregator((1, 5))
        instrument = InstrumentId.parse('CRYPTO:BINANCE:BTC-USDT')
        start = datetime(2026, 9, 11, 10, 0, 10, tzinfo=timezone.utc)

        aggregator.update(TradeTick(instrument, start, Decimal('100'), Decimal('2')))
        aggregator.update(TradeTick(
            instrument, start + timedelta(seconds=30), Decimal('102'), Decimal('3')
        ))
        minute_closed = aggregator.update(TradeTick(
            instrument, start + timedelta(minutes=1), Decimal('101'), Decimal('1')
        ))

        self.assertEqual(len(minute_closed), 1)
        self.assertEqual(minute_closed[0].timeframe, '1m')
        self.assertEqual(minute_closed[0].high, Decimal('102'))
        self.assertEqual(minute_closed[0].volume, Decimal('5'))

        five_closed = aggregator.update(TradeTick(
            instrument, start + timedelta(minutes=5), Decimal('105'), Decimal('1')
        ))
        self.assertEqual(
            {bar.timeframe for bar in five_closed},
            {'1m', '5m'},
        )

    def test_ignores_out_of_order_tick(self):
        aggregator = MultiTimeframeBarAggregator((1,))
        instrument = InstrumentId.parse('CRYPTO:BINANCE:BTC-USDT')
        timestamp = datetime(2026, 9, 11, 10, 0, tzinfo=timezone.utc)

        aggregator.update(TradeTick(instrument, timestamp, Decimal('100')))
        result = aggregator.update(TradeTick(
            instrument,
            timestamp - timedelta(seconds=1),
            Decimal('200'),
        ))
        closed = aggregator.update(TradeTick(
            instrument,
            timestamp + timedelta(minutes=1),
            Decimal('101'),
        ))

        self.assertEqual(result, [])
        self.assertEqual(closed[0].high, Decimal('100'))

if __name__ == '__main__':
    unittest.main()
