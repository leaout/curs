# coding: utf-8
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from curs import signal_recorder as journal
from curs.signal_opportunities import group_opportunities
from curs.signal_observer import report


class OpportunityTests(unittest.TestCase):
    def signal(self, strategy='old', time='2026-10-16T09:44:06+08:00', price=9):
        return {'order_id':strategy,'strategy_name':strategy,'timestamp':time,'stock_code':'002085.SZ',
                'signal_type':'BUY','price':price,'volume':100,'status':'SIGNAL_ONLY',
                'observations':[{'last_price_change_pct':5 if strategy=='old' else 2}]}

    def test_one_opportunity_retains_independent_strategy_observations(self):
        old = self.signal()
        new = self.signal('new','2026-10-16T09:45:06+08:00',9.2)
        grouped = group_opportunities([new,old])
        self.assertEqual(len(grouped),1)
        self.assertEqual(grouped[0]['strategy_count'],2)
        self.assertEqual(grouped[0]['price'],9)
        self.assertEqual(grouped[0]['volume'],100)
        self.assertEqual(grouped[0]['observations'][0]['last_price_change_pct'],5)
        self.assertEqual(grouped[0]['signals'][1]['observations'][0]['last_price_change_pct'],2)
        self.assertNotIn('opportunity_id',old)

    def test_distinct_day_direction_and_security_not_merged(self):
        rows=[self.signal(),dict(self.signal(),signal_type='SELL'),dict(self.signal(),stock_code='600001.SH'),
              self.signal('next','2026-10-17T09:44:06+08:00')]
        self.assertEqual(len(group_opportunities(rows)),4)

    def test_grouping_date_is_shanghai_not_utc(self):
        rows=[self.signal(time='2026-10-15T17:00:00+00:00'),self.signal('new','2026-10-16T01:01:00+08:00')]
        self.assertEqual(len(group_opportunities(rows)),1)

    def test_statuses_do_not_imply_additional_executions(self):
        rows=[self.signal(),dict(self.signal('new'),status='EXECUTED')]
        result=group_opportunities(rows)[0]
        self.assertEqual(result['status'],'MIXED')
        self.assertEqual(result['trigger_count'],2)

    def test_report_limit_never_cuts_off_group_member(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(journal,'JOURNAL_PATH',Path(directory)/'signals.sqlite3'):
            db=journal._connect()
            for row in [self.signal(),self.signal('new','2026-10-16T09:45:06+08:00',9.2)]:
                db.execute('INSERT INTO signals (order_id,trade_date,timestamp,strategy_name,stock_code,signal_type,price,volume) VALUES (?,?,?,?,?,?,?,?)',
                           (row['order_id'],'2026-10-16',row['timestamp'],row['strategy_name'],row['stock_code'],'BUY',row['price'],100))
            db.commit();db.close()
            result=report(limit=1)
            self.assertEqual(result['summary']['opportunity_count'],1)
            self.assertEqual(len(result['signals']),2)
            self.assertEqual(result['opportunities'][0]['trigger_count'],2)

    @patch('curs.stock_names.names_for', return_value={})
    @patch('web.app.get_db_manager')
    def test_api_grouping_and_raw_view_preserve_different_counts(self, manager, names):
        from web.app import app
        import copy
        rows=[self.signal(),self.signal('new','2026-10-16T09:45:06+08:00',9.2)]
        for row in rows:
            row['timestamp']=datetime.fromisoformat(row['timestamp'])
        manager.return_value.get_strategy_signals.side_effect=lambda **kwargs:copy.deepcopy(rows)
        with tempfile.TemporaryDirectory() as directory, patch.object(journal,'JOURNAL_PATH',Path(directory)/'signals.sqlite3'):
            client=app.test_client()
            grouped=client.get('/api/signals?view=opportunities&limit=1').get_json()
            self.assertEqual(grouped['total'],1)
            self.assertEqual(grouped['signals'][0]['trigger_count'],2)
            self.assertEqual(grouped['signals'][0]['price'],9)
            self.assertEqual(client.get('/api/signals').get_json()['total'],2)
            stats=client.get('/api/signals/stats').get_json()
            self.assertEqual(stats['total_signals'],1)
            self.assertEqual(stats['raw_signal_count'],2)
            self.assertEqual(stats['strategy_stats'],{'old':1,'new':1})


if __name__ == '__main__':
    unittest.main()
