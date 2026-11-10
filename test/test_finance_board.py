# coding: utf-8
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from curs import stock_intel


class FinanceBoardTests(unittest.TestCase):
    def test_market_report_is_unique_per_date_and_separate_from_stock_reports(self):
        day = '2026-11-09'
        report = {
            'assessment': '上涨 3000 家',
            'sources': [{'title': '市场数据', 'url': 'https://example.com/market'}],
        }
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(stock_intel, '_db_path', return_value=Path(folder) / 'intel.sqlite3'), \
                 patch.object(stock_intel, '_hot_pool', return_value=[]):
                self.assertTrue(stock_intel.claim_market_report(day))
                stock_intel.save_market_report(day, report)
                self.assertFalse(stock_intel.market_report_pending(day))
                self.assertFalse(stock_intel.claim_market_report(day))
                board = stock_intel.board_report(report_day=day)
                self.assertEqual(board['market_report']['assessment'], report['assessment'])
                self.assertEqual(board['agent_reports'], [])
                self.assertIsNone(stock_intel.market_report('2026-11-08'))
