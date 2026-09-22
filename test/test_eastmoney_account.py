# coding: utf-8
import importlib
import sys
import types
import unittest
from unittest.mock import patch


class FakeEastMoneyTradeAPI:
    def __init__(self, session_file):
        self.session_file = session_file
        self.orders = []

    def login(self, account_no, password):
        return {'success': True}

    def get_balance(self):
        return {
            'enable_balance': 8000.0,
            'frozen_balance': 2000.0,
            'market_value': 1200.0,
        }

    def get_positions(self):
        return [{
            'stock_code': '600000',
            'current_amount': 200,
            'enable_amount': 100,
            'cost_price': 5.0,
            'last_price': 6.0,
        }]

    def buy(self, stock_code, price, amount):
        self.orders.append(('buy', stock_code, price, amount))
        return {'success': True}

    def sell(self, stock_code, price, amount):
        self.orders.append(('sell', stock_code, price, amount))
        return {'success': True}

    def logout(self):
        return None


class TestEastMoneyAccount(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fake_api_module = types.ModuleType('curs.broker.eastmoney_trade_api')
        fake_api_module.EastMoneyTradeAPI = FakeEastMoneyTradeAPI
        cls.module_patch = patch.dict(sys.modules, {
            'curs.broker.eastmoney_trade_api': fake_api_module,
        })
        cls.module_patch.start()
        sys.modules.pop('curs.broker.eastmoney_account', None)
        cls.account_module = importlib.import_module('curs.broker.eastmoney_account')

    @classmethod
    def tearDownClass(cls):
        sys.modules.pop('curs.broker.eastmoney_account', None)
        cls.module_patch.stop()

    def setUp(self):
        self.account = self.account_module.EastMoneyAccount(
            account_no='12345678',
            password='secret',
            session_file='data/test.session',
        )

    def test_standard_position_and_asset_fields(self):
        position = self.account.get_positions()[0]
        asset = self.account.get_current_account()

        self.assertEqual(position.stock_code, '600000.SH')
        self.assertEqual(position.volume, 200)
        self.assertEqual(position.can_use_volume, 100)
        self.assertEqual(position.market_value, 1200.0)
        self.assertEqual(asset.cash, 8000.0)
        self.assertEqual(asset.total_asset, 11200.0)

    def test_sell_uses_only_available_t_plus_one_position(self):
        self.assertFalse(self.account.sell_fix_price('600000.SH', 200, 6.0))
        self.assertTrue(self.account.sell_fix_price('600000.SH', 100, 6.0))
        self.assertEqual(
            self.account._api.orders[-1],
            ('sell', '600000', 6.0, 100),
        )

    def test_liquidate_all_uses_available_position(self):
        results = self.account.liquidate_all_positions()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['stock_code'], '600000.SH')
        self.assertEqual(results[0]['volume'], 100)
        self.assertEqual(
            self.account._api.orders[-1],
            ('sell', '600000', 0, 100),
        )


if __name__ == '__main__':
    unittest.main()
