# coding: utf-8
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from curs import signal_recorder as journal
from curs.broker.public_quote import SHANGHAI
from curs.market_sentiment import analyze, a_share_code, board, fetch_universe, persist, stored, report, MarketSentimentMonitor


class SentimentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = patch.object(journal, 'JOURNAL_PATH', Path(self.temp.name) / 'signals.sqlite3')
        self.path.start()
        self.now = datetime(2026, 10, 9, 10, tzinfo=SHANGHAI)
        self.universe = {'source': 'test', 'securities': {'600001.SH': {}, '300001.SZ': {}, '688001.SH': {}, '920001.BJ': {}}}

    def tearDown(self):
        self.path.stop()
        self.temp.cleanup()

    def quote(self, price=11, time=None, name='普通股份'):
        return {'info': {'name': name, 'limit_up_price': 11, 'limit_down_price': 9},
                'tick': {'time': int((time or self.now).timestamp()*1000), 'lastPrice': price, 'lastClose': 10,
                         'high': 11, 'open': 9.9, 'amount': 100000}}

    def test_boards_and_beijing_new_codes(self):
        self.assertEqual(a_share_code('689009', 1), '689009.SH')
        self.assertEqual(board('689009.SH'), 'star')
        self.assertEqual(a_share_code('302132', 0), '302132.SZ')
        self.assertEqual(board('302132.SZ'), 'chinext')
        self.assertEqual(a_share_code('920001', 0), '920001.BJ')
        self.assertEqual(board('688001.SH'), 'star')
        with self.assertRaises(ValueError):
            a_share_code('510300', 1)

    @patch('curs.market_sentiment.requests.get')
    def test_universe_accepts_689_security_in_paginated_response(self, get):
        responses = []
        for page in range(10):
            response = MagicMock()
            rows = [{'f12': str(600000 + page * 100 + i), 'f13': 1, 'f14': '股份'} for i in range(100)]
            if page == 3:
                rows[0] = {'f12': '689009', 'f13': 1, 'f14': '九号公司-WD'}
            response.json.return_value = {'rc': 0, 'data': {'total': 1000, 'diff': rows}}
            responses.append(response)
        get.side_effect = responses
        result = fetch_universe()
        self.assertEqual(result['securities']['689009.SH']['board'], 'star')
        self.assertEqual(len(result['securities']), 1000)

    def test_coverage_filters_stale_future_and_unknown(self):
        records = {'600001.SH': self.quote(), '300001.SZ': self.quote(time=self.now-timedelta(minutes=10)),
                   '688001.SH': self.quote(time=self.now+timedelta(seconds=1)), '999999.SH': self.quote()}
        result = analyze(self.now, self.universe, records)
        self.assertEqual(result['coverage'], .25)
        self.assertEqual(result['state'], '数据不足')
        self.assertEqual(result['boards']['star']['samples'], 0)

    def test_cohort_ladder_and_missing_members_not_failures(self):
        cohort = {'day': '2026-10-08', 'members': {'600001.SH': {'height': 1}, '300001.SZ': {'height': 2}, '688001.SH': {'height': 2}}}
        records = {'600001.SH': self.quote(), '300001.SZ': self.quote(9.4)}
        result = analyze(self.now, self.universe, records, cohort)
        prior = result['prior_limit_up']
        self.assertAlmostEqual(prior['coverage'], 2/3)
        self.assertEqual(prior['ladder'][0]['promotion_ratio_observed'], 1)
        self.assertEqual(prior['ladder'][1]['observed'], 1)
        self.assertEqual(prior['severe_loss_ratio'], .5)
        self.assertFalse(result['data_ready'])

    def test_risk_names_excluded_not_hidden_in_coverage(self):
        records = {code: self.quote(name='ST股份' if code.startswith('600') else '普通股份') for code in self.universe['securities']}
        result = analyze(self.now, self.universe, records)
        self.assertEqual(result['coverage'], 1)
        self.assertEqual(result['breadth']['samples'], 3)
        self.assertEqual(result['excluded_risk_names'], 1)

    def test_cohort_is_immutable_and_journal_survives_reconnect(self):
        persist('market_cohorts', '2026-10-08', {'members': {'original': {}}}, immutable=True)
        persist('market_cohorts', '2026-10-08', {'members': {'future_winner': {}}}, immutable=True)
        self.assertIn('original', stored('market_cohorts', '2026-10-08')['members'])
        persist('sentiment_snapshots', self.now.isoformat(), {'timestamp': self.now.isoformat(), 'state': '数据不足'})
        self.assertEqual(len(report()['snapshots']), 1)

    @patch('curs.market_sentiment.requests.get')
    def test_duplicate_pagination_rejected(self, get):
        response = MagicMock()
        response.json.return_value = {'rc': 0, 'data': {'total': 1000, 'diff': [{'f12':'600001','f13':1,'f14':'股份'}]}}
        get.return_value = response
        with self.assertRaises(ValueError):
            fetch_universe()
        self.assertEqual(get.call_count, 2)

    @patch('curs.market_sentiment.fetch_universe')
    def test_weekend_does_not_fetch(self, fetch):
        monitor = MarketSentimentMonitor()
        monitor.poll_once(datetime(2026, 10, 10, 10, tzinfo=SHANGHAI))
        fetch.assert_not_called()
        self.assertEqual(monitor.status['reason'], '非交易采集时段')

    def test_complete_data_waits_for_trend_not_single_point_prediction(self):
        records = {code: self.quote() for code in self.universe['securities']}
        cohort = {'day': '2026-10-08', 'members': {c: {'height': 1} for c in records}}
        result = analyze(self.now, self.universe, records, cohort)
        self.assertTrue(result['data_ready'])
        self.assertEqual(result['state'], '待积累趋势')
        self.assertTrue(result['not_prediction'])

    @patch('curs.market_sentiment.requests.get')
    def test_complete_universe_requires_all_pages(self, get):
        responses = []
        for page in range(10):
            response = MagicMock()
            response.json.return_value = {'rc': 0, 'data': {'total': 1000, 'diff': [
                {'f12': str(600000+page*100+i), 'f13': 1, 'f14': '股份'} for i in range(100)]}}
            responses.append(response)
        get.side_effect = responses
        result = fetch_universe()
        self.assertEqual(len(result['securities']), 1000)
        self.assertEqual(get.call_count, 10)


if __name__ == '__main__':
    unittest.main()
