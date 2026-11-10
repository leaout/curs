# coding: utf-8
import unittest
from unittest.mock import patch

from curs.stock_names import enrich


class StockNameTests(unittest.TestCase):
    @patch('curs.stock_names.names_for', return_value={'002254.SZ':'泰和新材', '603065.SH':'宿迁联盛'})
    def test_historical_signals_and_candidates_enriched(self, lookup):
        payload = {'signals':[{'stock_code':'002254.SZ'}], 'candidates':[{'code':'603065.SH'}]}
        result = enrich(payload)
        self.assertEqual(result['signals'][0]['stock_label'], '002254.SZ 泰和新材')
        self.assertEqual(result['candidates'][0]['stock_name'], '宿迁联盛')

    @patch('curs.stock_names.names_for', return_value={'002254.SZ':None})
    def test_existing_name_preserved_and_missing_explicit(self, lookup):
        rows = [{'stock_code':'002254.SZ','stock_name':'记录名称'}, {'stock_code':'002254.SZ'}]
        result = enrich(rows)
        self.assertEqual(result[0]['stock_label'], '002254.SZ 记录名称')
        self.assertEqual(result[1]['stock_label'], '002254.SZ 名称暂缺')


if __name__ == '__main__':
    unittest.main()
