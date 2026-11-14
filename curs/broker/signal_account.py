# coding: utf-8
"""Account compatibility for strategies that only record signals."""

from curs.broker.account import Account


class SignalAccount(Account):
    signal_only = True

    @property
    def live_trading(self):
        return False

    @live_trading.setter
    def live_trading(self, enabled):
        if enabled:
            raise ValueError("当前仅记录信号，不支持实盘交易")

    def buy(self, *args, **kwargs):
        return False

    def sell(self, *args, **kwargs):
        return False

    buy_fix_price = buy
    buy_latest_price = buy
    sell_fix_price = sell
    sell_latest_price = sell

    def query_stock_positions(self):
        return []

    def query_stock_orders(self):
        return []

    def query_stock_trades(self):
        return []
