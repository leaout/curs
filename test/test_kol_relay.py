# coding: utf-8
import csv
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from curs import signal_recorder as journal
from curs.broker.public_quote import SHANGHAI
from curs.kol_intent.relay_context import import_csv, contexts, classify


class KOLRelayTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name)
        self.patch=patch.object(journal,'JOURNAL_PATH',self.folder/'signals.sqlite3')
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.now=datetime(2026,10,26,10,tzinfo=SHANGHAI)

    def ingest(self, rows, now=None):
        path=self.folder/'posts.csv'
        with path.open('w',encoding='utf-8',newline='') as output:
            writer=csv.DictWriter(output,fieldnames=['author','source_url','published_at','stock_code','text'])
            writer.writeheader()
            for row in rows:
                writer.writerow(dict(author=row[0],source_url='https://xueqiu.com/123/456',
                                     published_at=(self.now-timedelta(hours=1)).isoformat(),
                                     stock_code='600001.SH',text=row[1]))
        return import_csv(path,now or self.now)

    def opinion(self, when=None):
        return contexts(['600001.SH'],when or self.now+timedelta(seconds=1))['600001.SH']

    def test_first_seen_prevents_backfill_and_duplicates_preserve_time(self):
        self.ingest([('a','买入')])
        self.assertEqual(self.opinion(self.now)['assessment'],'无有效信息')
        result=self.ingest([('a','买入')],self.now+timedelta(hours=1))
        self.assertEqual(result['duplicates'],1)
        self.assertEqual(self.opinion()['assessment'],'明确支持')
        self.assertEqual(self.opinion()['evidence'][0]['collected_at'],self.now.isoformat())

    def test_reposts_retrospective_and_conditional_are_not_support(self):
        for text in ('昨天买入','转发 看多','如果突破就买入','持仓看多','不要再买入','不再看多','考虑加仓'):
            self.assertEqual(classify(text)[1],'neutral',text)

    def test_copy_dedup_and_opposition(self):
        self.ingest([('a','买入'),('b','买入'),('c','看空')])
        result=self.opinion()
        self.assertEqual(result['supporting'],1)
        self.assertEqual(result['opposing'],1)
        self.assertEqual(result['assessment'],'明确分歧')

    def test_latest_author_direction_and_expiry(self):
        self.ingest([('a','买入')])
        self.ingest([('a','看空')],self.now+timedelta(minutes=1))
        result=self.opinion(self.now+timedelta(minutes=2))
        self.assertEqual(result['assessment'],'明确分歧')
        self.assertEqual(result['supporting'],0)
        self.assertEqual(self.opinion(self.now+timedelta(days=3))['assessment'],'无有效信息')

    def test_no_cross_stock_contamination(self):
        self.ingest([('a','买入')])
        self.assertEqual(contexts(['600002.SH'],self.now+timedelta(seconds=1))['600002.SH']['assessment'],'无有效信息')

    def test_future_publication_rejected_and_empty_source_neutral(self):
        with self.assertRaises(ValueError):
            self.ingest([('a','买入')],self.now-timedelta(hours=2))
        self.assertEqual(self.opinion()['assessment'],'无有效信息')
        from curs.kol_intent.relay_context import stamp
        with self.assertRaises(ValueError):
            stamp('2026-10-26 09:00:00')

    def test_original_observation_is_not_rewritten_after_import(self):
        from curs.relay import RelayMonitor, report
        cohort={'day':'2026-10-23','members':{'600001.SH':{'height':1}}}
        snapshot={'data_ready':False,'prior_limit_up':{'day':'2026-10-23'}}
        monitor=RelayMonitor()
        monitor.scan(self.now,{},cohort,snapshot)
        self.ingest([('a','看空')],self.now+timedelta(seconds=1))
        monitor.scan(self.now,{},cohort,snapshot)
        self.assertEqual(report()['observations'][0]['kol_context']['assessment'],'无有效信息')

    def test_relay_risk_not_overridden(self):
        from curs.relay import RelayMonitor
        self.ingest([('a','买入')])
        monitor=RelayMonitor()
        cohort={'day':'2026-10-23','finalized':True,'members':{'600001.SH':{'height':1}}}
        snapshot={'data_ready':False,'prior_limit_up':{'day':'2026-10-23'}}
        now=self.now+timedelta(seconds=1)
        with patch.object(journal,'record_signal') as record:
            monitor.scan(now,{},cohort,snapshot)
            from curs.relay import report
            result=report()['observations'][0]
            self.assertEqual(result['status'],'待观察')
            self.assertEqual(result['kol_context']['assessment'],'明确支持')
            self.assertEqual(result['kol_shadow_status'],'待观察')
            record.assert_not_called()
