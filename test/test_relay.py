# coding: utf-8
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from curs import signal_recorder as journal
from curs.broker.public_quote import SHANGHAI
from curs.relay import RelayMonitor, report


class RelayTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,23,10,tzinfo=SHANGHAI)
        self.cohort={'day':'2026-10-22','finalized':True,'members':{'600001.SH':{'height':1,'name':'测试股份'}}}
        self.snapshot={'data_ready':True,'prior_limit_up':{'day':'2026-10-22','median_change_pct':2}}
        self.monitor=RelayMonitor({'groups':{'题材':['600001.SH','600002.SH','600003.SH']}})

    def records(self, now, price=11, amount=100):
        return {c:{'info':{'name':'测试股份','limit_up_price':11},'tick':{'time':now.timestamp()*1000,
                'lastPrice':price,'lastClose':10,'amount':amount,'open':10.1,'low':10}}
                for c in ('600001.SH','600002.SH','600003.SH')}

    def test_confirmation_requires_theme_and_multiple_samples(self):
        for seconds in (0,120,240):
            now=self.now+timedelta(seconds=seconds)
            row=self.monitor.evaluate(now,self.records(now,amount=100+seconds),self.cohort,self.snapshot)[0]
        self.assertEqual(row['status'],'影子条件通过')
        row=RelayMonitor().evaluate(now,self.records(now),self.cohort,self.snapshot)[0]
        self.assertEqual(row['status'],'待观察')
        self.assertIsNone(row['evidence']['theme'])

    def test_duplicate_stale_and_missing_cohort(self):
        records=self.records(self.now)
        for seconds in (0,60,120):
            row=self.monitor.evaluate(self.now+timedelta(seconds=seconds),records,self.cohort,self.snapshot)[0]
        self.assertEqual(row['evidence']['samples'],1)
        row=self.monitor.evaluate(self.now+timedelta(seconds=181),records,self.cohort,self.snapshot)[0]
        self.assertIn('个股行情缺失或过期',row['reasons'])
        self.assertEqual(self.monitor.evaluate(self.now,{},dict(self.cohort,finalized=False),self.snapshot),[])

    def test_stages_and_bad_environment(self):
        self.snapshot['state']='退潮风险观察'
        for height, stage in ((1,'一进二'),(2,'二进三'),(4,'高位接力')):
            self.cohort['members']['600001.SH']['height']=height
            row=self.monitor.evaluate(self.now,self.records(self.now),self.cohort,self.snapshot)[0]
            self.assertEqual(row['stage'],stage)
            self.assertIn('昨日涨停负反馈，环境否决',row['reasons'])

    def test_breaks_and_gap(self):
        for seconds,price in ((0,11),(120,10.8),(240,11),(360,10.8),(480,11),(600,11),(720,11)):
            now=self.now+timedelta(seconds=seconds)
            row=self.monitor.evaluate(now,self.records(now,price,100+seconds),self.cohort,self.snapshot)[0]
        self.assertIn('已观察到多次开板',row['reasons'])
        now=self.now+timedelta(seconds=1000)
        row=self.monitor.evaluate(now,self.records(now),self.cohort,self.snapshot)[0]
        self.assertEqual(row['evidence']['samples'],1)

    def test_storage_idempotent_no_signal(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(journal,'JOURNAL_PATH',Path(folder)/'signals.sqlite3'), patch.object(journal,'record_signal') as record:
            for _ in range(2):
                self.monitor.scan(self.now,self.records(self.now),self.cohort,self.snapshot)
            self.assertEqual(len(report()['observations']),1)
            record.assert_not_called()
