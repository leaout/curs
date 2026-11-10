# coding: utf-8
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from curs import signal_recorder as journal
from curs.broker.public_quote import SHANGHAI
from curs.first_board import FirstBoardMonitor, candidates


class FirstBoardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = patch.object(journal, 'JOURNAL_PATH', Path(self.temp.name) / 'signals.sqlite3')
        self.path.start()
        self.now = datetime(2026, 10, 9, 10, tzinfo=SHANGHAI)
        self.monitor = FirstBoardMonitor()
        self.monitor.eligibility['600001.SH'] = (True, 'ok')
        self.monitor.day = self.now.date()

    def tearDown(self):
        self.path.stop()
        self.temp.cleanup()

    def rows(self, seconds, price=11):
        now = self.now + timedelta(seconds=seconds)
        row = {'info': {'name': '普通股份', 'limit_up_price': 11},
               'tick': {'lastPrice': price, 'lastClose': 10, 'time': int(now.timestamp()*1000), 'amount': 10000+seconds*100}}
        return now, {'600001.SH': row, **{f'60000{i}.SH': {'info': {'name': '同行', 'limit_up_price': 11},
                    'tick': dict(row['tick'], lastPrice=10.4)} for i in (2, 3, 4)}}

    @patch('curs.first_board.journal.record_signal', return_value=True)
    def test_continuous_confirmation_only_once(self, record):
        for seconds in range(0, 81, 10):
            now, rows = self.rows(seconds)
            self.monitor.scan(now, rows, True)
        record.assert_called_once()
        self.assertEqual(candidates()[0]['state'], 'confirmed')

    @patch('curs.first_board.journal.record_signal')
    def test_gap_and_data_failure_reset(self, record):
        for seconds in (0, 10, 50, 60):
            now, rows = self.rows(seconds)
            self.monitor.scan(now, rows, True)
        record.assert_not_called()
        self.monitor.scan(now, rows, False)
        self.assertEqual(self.monitor.states, {})
        self.assertEqual(candidates()[0]['state'], 'paused')

    @patch('curs.first_board.journal.record_signal')
    def test_open_board_and_insufficient_peers(self, record):
        now, rows = self.rows(0)
        self.monitor.scan(now, rows, True)
        now, rows = self.rows(10, 10.95)
        self.monitor.scan(now, rows, True)
        self.assertEqual(self.monitor.states, {})
        self.monitor.scan(now, {'600001.SH': rows['600001.SH']}, True)
        record.assert_not_called()

    def test_history_rejects_previous_limit_up_and_missing_bars(self):
        self.monitor.bars = lambda *args, **kwargs: {'dates': ['2026-10-01','2026-10-02','2026-10-03','2026-10-04','2026-10-05','2026-10-08'],
                                                   'kline_data': [[9,9,9,9]]*5 + [[10,10,10,10]]}
        self.assertFalse(self.monitor.check_history('600001.SH', {'lastClose': 10}, self.now)[0])
        self.monitor.bars = lambda *args, **kwargs: None
        self.assertFalse(self.monitor.check_history('600001.SH', {'lastClose': 10}, self.now)[0])


if __name__ == '__main__':
    unittest.main()
