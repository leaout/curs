# coding: utf-8
import unittest
from unittest.mock import MagicMock, patch

from curs.database import DatabaseManager


class SnapshotTests(unittest.TestCase):
    def test_legacy_records_have_unknown_height(self):
        db = DatabaseManager()
        db.execute_query = MagicMock(side_effect=[[], [{'stock_code':'600001.SH', 'snapshot':None}]])
        result = db.get_zt_snapshot('2026-10-12')
        self.assertFalse(result['finalized'])
        self.assertIsNone(result['members']['600001.SH']['height'])

    def test_partial_batch_is_rejected(self):
        db = DatabaseManager()
        row = {'stock_code':'600001.SH','snapshot':{'recorded_at':'2026-10-12T16:00:00','batch_id':'a','expected':2,'height':1}}
        db.execute_query = MagicMock(side_effect=[[{'column_name':'snapshot'}], [row]])
        with self.assertRaises(ValueError):
            db.get_zt_snapshot('2026-10-12')

    @patch('curs.database.psycopg2.connect')
    def test_snapshot_write_uses_transaction_and_existing_table(self, connect):
        db = DatabaseManager()
        db.save_zt_snapshot('2026-10-12', {'600001.SH':{'height':1,'name':'测试'}}, 'test')
        cursor = connect.return_value.cursor.return_value.__enter__.return_value
        self.assertIn('ALTER TABLE zt_stocks', cursor.execute.call_args_list[0].args[0])
        self.assertIn('ON CONFLICT', cursor.execute.call_args_list[1].args[0])
        connect.return_value.__enter__.assert_called_once()
        connect.return_value.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
