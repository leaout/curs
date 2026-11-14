# coding: utf-8
import runpy
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from curs.broker import create_account
from curs.broker.public_quote import PublicQuoteEngine, SHANGHAI, normalize_code, parse_quote
from curs.events import EVENT, Event, EventBus
from curs.signal_recorder import record_signal, flush_pending_signals


class PublicQuoteTests(unittest.TestCase):
    def quote_line(self):
        fields = ['0'] * 49
        for index, value in {1: '测试股份', 2: '600001', 3: '10.90', 4: '10', 5: '10.10',
                             6: '1000', 30: '20261008100000', 33: '10.95', 34: '10',
                             37: '100', 47: '11', 48: '9'}.items():
            fields[index] = value
        for index in range(9, 29, 2):
            fields[index], fields[index + 1] = '10.90', '100'
        return 'v_sh600001="' + '~'.join(fields) + '";'

    def test_parse_real_field_positions(self):
        row = parse_quote(self.quote_line())
        self.assertEqual(row['info']['name'], '测试股份')
        self.assertEqual(row['info']['limit_up_price'], 11)
        self.assertEqual(row['tick']['amount'], 1000000)
        self.assertEqual(len(row['tick']['askPrice']), 5)
        self.assertEqual(row['tick']['askVol'], [100] * 5)
        self.assertEqual(datetime.fromtimestamp(row['tick']['time'] / 1000, SHANGHAI).hour, 10)

    def test_invalid_or_unpriced_response_is_rejected(self):
        for line in ['v_sh600001="";', self.quote_line().replace('~10.90~', '~nan~', 1)]:
            with self.assertRaises(ValueError):
                parse_quote(line)

    def test_codes(self):
        self.assertEqual(normalize_code('stock_sh_600001'), '600001.SH')
        self.assertEqual(normalize_code('sz000001'), '000001.SZ')
        with self.assertRaises(ValueError):
            normalize_code('invalid')

    @patch('curs.signal_observer.observe')
    @patch('curs.signal_observer.watch_codes', return_value=[])
    @patch('curs.first_board.FirstBoardMonitor.scan')
    def test_quotes_are_fresh_and_deduplicated(self, mocked_scan, mocked_codes, mocked_observe):
        bus = MagicMock()
        engine = PublicQuoteEngine(bus)
        now = datetime(2026, 10, 8, 10, tzinfo=SHANGHAI)
        engine._day = now.date()
        engine.stocks = ['600001.SH']
        row = parse_quote(self.quote_line())
        engine.provider = MagicMock()
        engine.provider.get_quotes.return_value = {'600001.SH': row}
        self.assertEqual(len(engine.poll_once(now)), 1)
        self.assertEqual(engine.poll_once(now), {})
        self.assertEqual(bus.put_event.call_count, 1)
        self.assertEqual(bus.put_event.call_args.args[0].event_type, EVENT.TICK)
        row['tick']['time'] = int((now - timedelta(minutes=3)).timestamp() * 1000)
        engine._last_times.clear()
        self.assertEqual(engine.poll_once(now), {})
        row['tick']['time'] = int((now + timedelta(minutes=1)).timestamp() * 1000)
        self.assertEqual(engine.poll_once(now), {})

    def test_network_failure_does_not_kill_event_dispatch(self):
        bus = EventBus()
        received = []
        bus.add_listener(EVENT.TICK, lambda event: 1 / 0)
        bus.add_listener(EVENT.TICK, lambda event: received.append(event.tick))
        with self.assertLogs('curs.events', level='ERROR'):
            bus.publish_event(Event(EVENT.TICK, tick={'600001.SH': {}}))
        self.assertEqual(len(received), 1)


class SignalOnlyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.journal = Path(self.temp.name) / 'signals.sqlite3'
        self.path_patch = patch('curs.signal_recorder.JOURNAL_PATH', self.journal)
        self.path_patch.start()
        self.manager = MagicMock()
        self.manager.execute_query.return_value = []
        self.manager.save_strategy_signal.return_value = True
        self.db_patch = patch('curs.signal_recorder.get_db_manager', return_value=self.manager)
        self.db_patch.start()
        self.context = SimpleNamespace(account=create_account({'broker': 'qmt'}),
                                       current_time=datetime(2026, 10, 8, 10), pre_limit_up_stocks=set())

    def tearDown(self):
        self.db_patch.stop()
        self.path_patch.stop()
        self.temp.cleanup()

    def count(self):
        with sqlite3.connect(self.journal) as db:
            return db.execute('SELECT count(*) FROM signals').fetchone()[0]

    def test_account_cannot_trade_even_with_old_broker_configuration(self):
        account = self.context.account
        self.assertFalse(account.live_trading)
        self.assertFalse(account.buy_fix_price('600001.SH', 100, 11))
        self.assertEqual(account.positions, {})
        with self.assertRaises(ValueError):
            account.live_trading = True

    def test_persistent_deduplication_and_next_day(self):
        record_signal(self.context, 'test_strategy', '600001.SH', 11, 100)
        record_signal(self.context, 'test_strategy', '600001.SH', 11, 100)
        self.assertEqual(self.count(), 1)
        flush_pending_signals()
        self.assertEqual(self.manager.save_strategy_signal.call_count, 1)
        self.assertEqual(self.manager.save_strategy_signal.call_args.kwargs['status'], 'SIGNAL_ONLY')
        self.context.current_time += timedelta(days=1)
        record_signal(self.context, 'test_strategy', '600001.SH', 11, 100)
        self.assertEqual(self.count(), 2)

    def test_database_outage_keeps_local_signal_and_retries(self):
        self.manager.execute_query.return_value = None
        record_signal(self.context, 'test_strategy', '600001.SH', 11, 100)
        self.assertEqual(self.count(), 1)
        self.manager.save_strategy_signal.assert_not_called()
        self.manager.execute_query.return_value = []
        flush_pending_signals()
        self.manager.save_strategy_signal.assert_called_once()

    def test_actual_limit_up_volume_drop_records_signal_without_order(self):
        scope = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'strategies' / 'limit_up_strategy.py'))
        context = self.context
        context.order_tracker = MagicMock()
        context.order_tracker.get_pending_orders.return_value = []
        context.profit_stats = MagicMock()
        context.pre_ticks = {}
        context.stock_base_info = {'600001.SH': {'name': '测试股份', 'limit_up_price': 11}}
        context.daily_signaled_stocks = set()
        context.hot_stocks = {'600001.SH'}
        context.last_order_volumes = {}
        context.open_time = datetime.strptime('09:35', '%H:%M').time()
        context.close_time = datetime.strptime('14:00', '%H:%M').time()
        tick = {'time': int(datetime(2026, 10, 8, 10, tzinfo=SHANGHAI).timestamp() * 1000),
                'lastPrice': 10.95, 'bidPrice': [10.95], 'askPrice': [11], 'askVol': [1000]}
        scope['handle_tick'](context, {'600001.SH': tick})
        tick = {**tick, 'askVol': [400]}
        scope['handle_tick'](context, {'600001.SH': tick})
        self.assertEqual(self.count(), 1)
        flush_pending_signals()
        self.manager.save_strategy_signal.assert_called_once()
        context.order_tracker.register_order.assert_not_called()
        context.profit_stats.record_buy.assert_not_called()
        self.assertFalse(context.account.positions)


if __name__ == '__main__':
    unittest.main()
