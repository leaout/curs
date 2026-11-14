# coding: utf-8
"""Deterministic research tests without network, model weights or databases."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from curs.kol_intent.baseline import generate_trades
from curs.kol_intent.data import prepare_prices
from curs.kol_intent.event_study import event_study
from curs.kol_intent.extractor import IntentExtractor
from curs.kol_intent.report import analyze, export_report


class KOLIntentTests(unittest.TestCase):
    def setUp(self):
        self.days = pd.bdate_range('2026-10-12', periods=12, tz='Asia/Shanghai')
        self.prices = prepare_prices(pd.DataFrame([
            dict(timestamp=day, ticker=ticker, open=100.0, close=100.0)
            for day in self.days for ticker in ('AAA', 'BBB')]))

    def posts(self, rows):
        return pd.DataFrame(rows, columns=['timestamp', 'ticker', 'text'])

    def test_finbert_failure_falls_back_and_filters(self):
        with patch.dict('sys.modules', {'torch': None}), self.assertLogs('curs.kol_intent.extractor', level='WARNING'):
            extractor = IntentExtractor()
        posts = self.posts([
            (self.days[0], 'AAA', 'buy AAA'), (self.days[0], 'BBB', '看空，减仓'),
            (self.days[0], 'MISSING', 'buy'), (self.days[0], 'AAA', 'not buy'),
            (self.days[0], 'AAA', 'buy and sell'), (self.days[0], 'AAA', 'good profit')])
        events, sentiment = extractor.extract(posts, {'AAA', 'BBB'})
        self.assertEqual(events['direction'].tolist(), ['long', 'short'])
        self.assertEqual(len(events.iloc[0]['text_embedding']), 64)
        self.assertEqual(events.iloc[0]['backend'], 'keywords')
        self.assertGreater(len(sentiment), len(events))

    def test_signal_dates_reversal_deduplication_and_holding_period(self):
        posts = self.posts([(self.days[0], 'AAA', 'buy'), (self.days[1], 'AAA', 'buy'),
                            (self.days[2], 'AAA', 'sell'), (self.days[0], 'BBB', '买入')])
        events, _ = IntentExtractor(False).extract(posts, {'AAA', 'BBB'})
        trades, daily = generate_trades(events, self.prices)
        aaa = trades[trades['ticker'] == 'AAA'].iloc[0]
        bbb = trades[trades['ticker'] == 'BBB'].iloc[0]
        self.assertEqual(len(trades), 2)
        self.assertEqual(aaa['entry_date'], self.days[1])
        self.assertEqual(aaa['exit_date'], self.days[3])
        self.assertEqual(aaa['reason'], 'short')
        self.assertEqual(bbb['exit_date'], self.days[6])
        self.assertEqual(daily['daily_return'].sum(), 0)

    def test_car_known_market_adjusted_path(self):
        prices = self.prices.copy()
        for index, day in enumerate(self.days):
            prices.loc[(prices['ticker'] == 'AAA') & (prices['timestamp'] == day), ['open', 'close']] = 100 * 1.02 ** index
        events, _ = IntentExtractor(False).extract(self.posts([(self.days[3], 'AAA', 'long')]), {'AAA'})
        study, curve = event_study(events, prices)
        self.assertAlmostEqual(study.iloc[0]['car'], .07)
        self.assertAlmostEqual(curve.iloc[-1]['mean_car'], .07)
        self.assertTrue(study.iloc[0]['complete_window'])

    def test_entry_excludes_prior_gap_and_exit_includes_overnight(self):
        prices = self.prices[self.prices['ticker'] == 'AAA'].copy()
        prices.loc[prices['timestamp'] >= self.days[1], ['open', 'close']] = 200
        prices.loc[prices['timestamp'] >= self.days[2], ['open', 'close']] = 220
        events, _ = IntentExtractor(False).extract(self.posts([(self.days[0], 'AAA', 'buy')]), {'AAA'})
        trades, daily = generate_trades(events, prices, holding_days=1)
        self.assertEqual(daily.iloc[1]['daily_return'], 0)
        self.assertAlmostEqual(daily.iloc[2]['daily_return'], .1)
        self.assertAlmostEqual(trades.iloc[0]['return'], .1)

    def test_missing_entry_exit_and_open_end(self):
        prices = self.prices[~((self.prices['ticker'] == 'AAA') &
                                  (self.prices['timestamp'] == self.days[6]))]
        events, _ = IntentExtractor(False).extract(self.posts([(self.days[0], 'AAA', 'buy')]), {'AAA'})
        trades, _ = generate_trades(events, prices)
        self.assertEqual(trades.iloc[0]['exit_date'], self.days[7])
        late, _ = IntentExtractor(False).extract(self.posts([(self.days[-2], 'AAA', 'buy')]), {'AAA'})
        trades, _ = generate_trades(late, prices)
        self.assertEqual(trades.iloc[0]['reason'], 'open_at_end')
        self.assertTrue(pd.isna(trades.iloc[0]['exit_date']))
        missing, _ = IntentExtractor(False).extract(self.posts([(self.days[5], 'AAA', 'buy')]), {'AAA'})
        trades, _ = generate_trades(missing, prices)
        self.assertTrue(trades.empty)

    def test_report_comparison_export_and_empty_events(self):
        posts = self.posts([(self.days[2], 'AAA', 'great profit'), (self.days[3], 'AAA', 'buy'),
                            (self.days[4], 'AAA', 'sell')])
        result = analyze(posts, self.prices, {'use_finbert': False})
        self.assertEqual(result['report']['intent']['uer'], 0)
        self.assertEqual(result['report']['sentiment']['uer'], 1)
        self.assertEqual(result['report']['intent']['drr'], 1)
        with tempfile.TemporaryDirectory() as directory:
            export_report(result, Path(directory))
            for filename in ('report.json', 'report.md', 'mean_car.png', 'trades.csv', 'intent_events.csv'):
                self.assertTrue((Path(directory) / filename).is_file())
        empty = analyze(self.posts([(self.days[0], 'AAA', 'no opinion')]), self.prices, {'use_finbert': False})
        self.assertIsNone(empty['report']['intent']['uer'])
        self.assertEqual(empty['report']['intent']['cumulative_return'], 0)
        self.assertTrue(empty['event_study'].empty)


if __name__ == '__main__':
    unittest.main()
