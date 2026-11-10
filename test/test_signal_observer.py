# coding: utf-8
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from curs import signal_recorder
from curs.broker.public_quote import PublicQuoteEngine, SHANGHAI
from curs.signal_observer import observe, report


class ObserverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path_patch = patch.object(signal_recorder, 'JOURNAL_PATH', Path(self.temp.name) / 'signals.sqlite3')
        self.path_patch.start()
        self.flush_patch = patch.object(signal_recorder, 'flush_pending_signals')
        self.flush_patch.start()
        self.now = datetime(2026, 10, 9, 10, tzinfo=SHANGHAI)

    def tearDown(self):
        self.flush_patch.stop()
        self.path_patch.stop()
        self.temp.cleanup()

    def record(self, price, now):
        return {'info': {'limit_up_price': 11, 'limit_down_price': 9},
                'tick': {'time': int(now.timestamp()*1000), 'lastPrice': price, 'lastClose': 10, 'amount': 10000, 'high': 11, 'low': 9}}

    def test_forward_extrema_exclude_pre_signal_high(self):
        health = {'data_ready': True, 'coverage': 1}
        observe(self.now, {'600001.SH': self.record(10, self.now)}, ['600001.SH'], health)
        signal_recorder.record_signal(SimpleNamespace(current_time=self.now.replace(tzinfo=None)), 'test', '600001.SH', 10, 100)
        observe(self.now, {'600001.SH': self.record(10, self.now)}, ['600001.SH'], health)
        self.assertEqual(report()['signals'][0]['observations'], [])
        later = self.now + timedelta(minutes=1)
        observe(later, {'600001.SH': self.record(10.2, later)}, ['600001.SH'], health)
        observe(later, {'600001.SH': self.record(10.2, later)}, ['600001.SH'], health)
        result = report()['signals'][0]
        self.assertEqual(result['environment']['state'], 'observe_only')
        self.assertEqual(result['observations'][0]['samples'], 1)
        self.assertEqual(result['observations'][0]['max_price'], 10.2)
        self.assertAlmostEqual(result['observations'][0]['last_price_change_pct'], 2)

    def test_low_coverage_blocks_events_and_recovers(self):
        bus = MagicMock()
        engine = PublicQuoteEngine(bus)
        engine._day = self.now.date()
        engine.stocks = ['600001.SH', '600002.SH']
        engine.provider = MagicMock()
        engine.provider.get_quotes.return_value = {'600001.SH': self.record(10, self.now)}
        self.assertEqual(engine.poll_once(self.now), {})
        self.assertFalse(engine._health['data_ready'])
        bus.put_event.assert_not_called()
        later = self.now + timedelta(minutes=1)
        engine.provider.get_quotes.return_value = {code: self.record(10, later) for code in engine.stocks}
        self.assertEqual(len(engine.poll_once(later)), 2)
        self.assertTrue(engine._health['data_ready'])
        engine.provider.get_quotes.return_value = {}
        engine.poll_once(later + timedelta(minutes=1))
        self.assertFalse(engine._health['data_ready'])
        self.assertEqual(engine._health['consecutive_failures'], 1)

    def test_observations_persist_and_missing_dates_not_filled(self):
        signal_recorder.record_signal(SimpleNamespace(current_time=self.now), 'test', '600001.SH', 10, 100)
        later = self.now + timedelta(days=3)
        observe(later, {'600001.SH': self.record(9, later)}, [], {'data_ready': False})
        observations = report()['signals'][0]['observations']
        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0]['day'], '2026-10-12')
        self.assertAlmostEqual(observations[0]['min_price_change_pct'], -10)


if __name__ == '__main__':
    unittest.main()
