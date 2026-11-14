# coding: utf-8
import sqlite3
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from curs import signal_recorder as journal
from curs.broker.public_quote import SHANGHAI
from curs.first_board import FirstBoardMonitor, candidates
from curs.strategy.strategy import Strategy
from data_collection.import_from_collected import find_latest_json, import_to_database


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'signals.sqlite3'
        self.path_patch = patch.object(journal, 'JOURNAL_PATH', self.path)
        self.path_patch.start()
        self.names = patch('curs.stock_names.names_for', return_value={})
        self.names.start()
        self.now = datetime(2026, 10, 14, 10, tzinfo=SHANGHAI)

    def tearDown(self):
        self.names.stop()
        self.path_patch.stop()
        self.temp.cleanup()

    @patch('curs.signal_recorder.flush_pending_signals')
    def test_signal_normalizes_utc_date_and_rejects_nonfinite(self, flush):
        context = SimpleNamespace(current_time=datetime(2026, 10, 13, 18, tzinfo=timezone.utc))
        self.assertFalse(journal.record_signal(context, 'test', '600001.SH', float('nan'), 100))
        self.assertFalse(journal.record_signal(context, 'test', '600001.SH', 10, float('inf')))
        journal.record_signal(context, 'test', '600001.SH', 10, 100)
        with sqlite3.connect(self.path) as db:
            row = db.execute('SELECT trade_date,timestamp FROM signals').fetchone()
        self.assertEqual(row[0], '2026-10-14')
        self.assertIn('02:00:00+08:00', row[1])

    @patch('curs.signal_recorder.get_db_manager')
    def test_postgres_mirror_does_not_hold_journal_lock(self, manager):
        db = journal._connect()
        db.execute('INSERT INTO signals VALUES (?,?,?,?,?,?,?,?,?,?)',
                   ('id','2026-10-14',self.now.isoformat(),'test','600001.SH','BUY',10,100,0,None))
        db.commit()
        db.close()
        acquired = []
        def query(*args):
            def check():
                ok = journal._lock.acquire(timeout=.5)
                acquired.append(ok)
                if ok:
                    journal._lock.release()
            thread = threading.Thread(target=check)
            thread.start()
            thread.join()
            return []
        manager.return_value.execute_query.side_effect = query
        manager.return_value.save_strategy_signal.return_value = True
        journal.flush_pending_signals()
        self.assertEqual(acquired, [True])

    def test_first_tick_is_not_discarded(self):
        handle = MagicMock()
        context = SimpleNamespace()
        strategy = Strategy(MagicMock(), {'handle_tick':handle}, context)
        event = SimpleNamespace(tick={'600001.SH':{}})
        strategy.handle_tick(event)
        handle.assert_called_once_with(context, event.tick)

    def test_confirmed_status_survives_price_fall_and_missing_data(self):
        monitor = FirstBoardMonitor()
        monitor.day = self.now.date()
        monitor._confirmed.add('600001.SH')
        monitor.save(self.now, '600001.SH', 'confirmed', 'confirmed')
        monitor.scan(self.now, {}, False)
        monitor.scan(self.now, {'600001.SH': {'tick':{'lastPrice':1},'info':{}}}, True)
        self.assertEqual(candidates()[0]['state'], 'confirmed')

    def test_missing_individual_quote_resets_confirmation(self):
        monitor = FirstBoardMonitor()
        monitor.day = self.now.date()
        monitor.states['600001.SH'] = {'start':1,'last':1}
        monitor.scan(self.now, {}, True)
        self.assertNotIn('600001.SH', monitor.states)
        self.assertEqual(candidates()[0]['state'], 'paused')

    @patch('data_collection.import_from_collected.glob.glob')
    def test_latest_hot_file_is_selected_by_data_date(self, glob):
        glob.return_value = ['data/collected/hot_stocks_20260612.json','data/collected/hot_stocks_20261013.json']
        self.assertTrue(find_latest_json().endswith('20261013.json'))

    @patch('data_collection.import_from_collected._get_connection')
    def test_import_failure_rolls_back_existing_pool(self, connection):
        cursor = connection.return_value.cursor.return_value
        cursor.execute.side_effect = [None, RuntimeError('insert failure')]
        result = import_to_database([{'code':'600001.SH','name':'测试'}])
        self.assertFalse(result['success'])
        connection.return_value.rollback.assert_called_once()
        connection.return_value.commit.assert_not_called()

    @patch('curs.broker.public_quote.get_stock_kline_data')
    @patch('web.app.get_db_manager')
    def test_legacy_profit_analysis_uses_public_unadjusted_bars(self, manager, bars):
        from web.app import app
        manager.return_value.get_executed_buy_signals.return_value = [{'stock_code':'600001.SH','stock_name':'测试',
            'price':10, 'timestamp':datetime(2026,10,12,10,tzinfo=SHANGHAI)}]
        bars.return_value = {'dates':['2026-10-12','2026-10-13'], 'kline_data':[[10,10,9,10],[9,9,8,9.5]]}
        response = app.test_client().get('/api/signals/profit-analysis?price_type=close')
        self.assertEqual(response.status_code, 200)
        self.assertAlmostEqual(response.get_json()['details'][0]['max_profit_pct'], -10)
        self.assertEqual(bars.call_args.kwargs['adjustment'], '')

    @patch('web.app.get_db_manager')
    def test_signal_api_displays_shanghai_not_utc(self, manager):
        from web.app import app
        manager.return_value.get_strategy_signals.return_value = [{'stock_code':'600001.SH',
            'timestamp':datetime(2026,10,13,5,23,tzinfo=timezone.utc)}]
        response = app.test_client().get('/api/signals')
        self.assertEqual(response.get_json()['signals'][0]['timestamp'], '2026-10-13 13:23:00')

    @patch('web.app.get_db_manager')
    def test_local_pending_signal_remains_visible_without_database(self, manager):
        from web.app import app
        manager.return_value.get_strategy_signals.return_value = None
        journal.record_signal(SimpleNamespace(current_time=self.now), 'pending', '600001.SH', 10, 100)
        response = app.test_client().get('/api/signals?strategy=pending')
        signals = response.get_json()['signals']
        self.assertEqual(len(signals), 1)
        self.assertTrue(signals[0]['mirror_pending'])
        stats = app.test_client().get('/api/signals/stats').get_json()
        self.assertEqual(stats['total_signals'], 1)

    def test_environment_in_same_minute_cannot_leak_future_information(self):
        from curs.signal_observer import observe, capture_context, report
        observe(self.now + timedelta(seconds=50), {}, [], {'data_ready':False})
        journal.record_signal(SimpleNamespace(current_time=self.now), 'test', '600001.SH', 10, 100)
        result = report()['signals'][0]
        self.assertEqual(result['environment']['state'], 'unknown')

    @patch('web.app.get_db_manager')
    def test_local_canonical_time_corrects_legacy_naive_database_mirror(self, manager):
        from web.app import app
        journal.record_signal(SimpleNamespace(current_time=self.now), 'test', '600001.SH', 10, 100)
        local = journal.local_signals()[0]
        manager.return_value.get_strategy_signals.return_value = [dict(local, timestamp=datetime(2026,10,14,2),status='SIGNAL_ONLY')]
        response = app.test_client().get('/api/signals')
        self.assertEqual(response.get_json()['signals'][0]['timestamp'], '2026-10-14 10:00:00')

    @patch('data_collection.import_from_collected.import_to_database')
    @patch('data_collection.import_from_collected.load_stocks_from_file')
    @patch('data_collection.import_from_collected.find_latest_json')
    def test_renamed_recent_file_cannot_import_old_collected_records(self, latest, load, importer):
        from data_collection.import_from_collected import main
        today = datetime.now(SHANGHAI).strftime('%Y%m%d')
        latest.return_value = 'hot_stocks_' + today + '.json'
        load.return_value = [{'code':'600001.SH','collect_time':'2026-01-01T12:00:00'}]
        main()
        importer.assert_not_called()


if __name__ == '__main__':
    unittest.main()
