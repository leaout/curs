# coding: utf-8
import unittest
from datetime import datetime, timezone
from decimal import Decimal

from trading_v2.domain.market import AssetClass, InstrumentId
from trading_v2.market.cpptdx import CppTdxMarketDataProvider


class StubRequest:
    def __init__(self):
        self.calls = []

    async def __call__(self, url, params):
        self.calls.append((url, params))
        if url.endswith('/health'):
            return {'status': 'ok'}
        if url.endswith('/api/snapshots'):
            return [{
                'market': 1,
                'code': '600000',
                'price': 10.84,
                'last_close': 10.70,
                'open': 10.72,
                'high': 10.91,
                'low': 10.68,
                'datetime': 103000000,
                'vol': 200000,
                'amount': 2168000,
                'bid1': 10.83,
                'ask1': 10.84,
            }]
        if url.endswith('/api/klines'):
            return [
                {'datetime': 202609210935, 'open': 10.70, 'high': 10.75,
                 'low': 10.68, 'close': 10.73, 'vol': 1000, 'amount': 10720},
                {'datetime': 202609210930, 'open': 10.65, 'high': 10.72,
                 'low': 10.64, 'close': 10.70, 'vol': 900, 'amount': 9600},
            ]
        raise AssertionError(url)


class CppTdxProviderTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.request = StubRequest()
        self.provider = CppTdxMarketDataProvider(request=self.request)
        self.instrument = InstrumentId(
            symbol='600000', venue='XSHG', asset_class=AssetClass.CN_EQUITY
        )

    async def test_health(self):
        result = await self.provider.health()
        self.assertTrue(result.healthy)
        self.assertEqual('cpptdx', result.source)

    async def test_snapshot_normalization(self):
        result = await self.provider.get_snapshots([self.instrument])
        self.assertEqual(1, len(result))
        self.assertEqual('10.84', str(result[0].last))
        self.assertEqual('cpptdx', result[0].source)
        self.assertEqual(timezone.utc, result[0].market_time.tzinfo)

    async def test_kline_normalization_and_sorting(self):
        bars = await self.provider.get_bars(self.instrument, '5m', 2)
        self.assertEqual(2, len(bars))
        self.assertLess(bars[0].open_time, bars[1].open_time)
        self.assertEqual(Decimal('10.70'), bars[0].close)
        self.assertIsInstance(bars[0].open_time, datetime)

    async def test_rejects_unsupported_market(self):
        instrument = InstrumentId(
            symbol='BTC-USDT', venue='BINANCE', asset_class=AssetClass.CRYPTO
        )
        with self.assertRaises(ValueError):
            await self.provider.get_snapshots([instrument])


if __name__ == '__main__':
    unittest.main()
