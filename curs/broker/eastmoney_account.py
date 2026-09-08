# coding: utf-8
"""
东方财富证券 Broker 适配层
封装 eastmoney_trade_api.py，实现与 QmtStockAccount 兼容的接口
"""

import math
import time
import logging
from datetime import datetime

from curs.broker.account import Account, Position
from curs.broker.eastmoney_trade_api import EastMoneyTradeAPI

logger = logging.getLogger(__name__)


class EastMoneyAccount(Account):
    """
    东方财富证券交易账户
    对接 jywg.18.cn 网关，支持限价单交易
    """

    def __init__(self, account_no: str, password: str,
                 session_file: str = "eastmoney_trader.session",
                 total_cash: float = 0):
        super().__init__(total_cash)

        self._live_trading = True
        self.account_no = account_no
        self._api = EastMoneyTradeAPI(session_file=session_file)
        self._api.login(account_no=account_no, password=password)

        # 从东方财富同步真实资金和持仓
        self._sync_balance()

        logger.info(f"东方财富账户登录成功: {account_no}")

    # ─── live_trading 属性（与 QmtStockAccount 一致）──────────

    @property
    def live_trading(self):
        return self._live_trading

    @live_trading.setter
    def live_trading(self, value):
        self._live_trading = value
        logger.info(f"实盘交易{'已开启' if value else '已关闭'}")

    # ─── 资金同步 ──────────────────────────────────────────

    def _sync_balance(self):
        """从东方财富同步资金和持仓到本地 Account 基类"""
        try:
            balance = self._api.get_balance()
            self._total_cash = balance['enable_balance'] + balance['frozen_balance']
            self._frozen_cash = balance['frozen_balance']

            # 同步持仓
            api_positions = self._api.get_positions()
            for p in api_positions:
                code = p['stock_code']
                # 东方财富返回的是6位纯代码，需要加上交易所后缀
                code_with_suffix = self._to_xt_code(code)
                pos = self.positions.get(code_with_suffix)
                if pos is None:
                    pos = Position()
                    self.positions[code_with_suffix] = pos
                pos.quantity = p['current_amount']
                pos.avg_price = p['cost_price']
                pos._last_price = p['last_price']
                pos._non_closable = p['current_amount'] - p['enable_amount']

            logger.debug(f"资金同步: 可用{balance['enable_balance']:.2f} 市值{balance['market_value']:.2f}")
        except Exception as e:
            logger.error(f"资金同步失败: {e}")

    @staticmethod
    def _to_xt_code(stock_code: str) -> str:
        """
        东方财富6位代码 → xtquant 格式（带交易所后缀）
        600xxx, 601xxx, 603xxx, 605xxx → .SH
        000xxx, 001xxx, 002xxx, 300xxx → .SZ
        400xxx, 8xxxxx → .BJ
        """
        if len(stock_code) == 9 and stock_code[-3] == '.':
            return stock_code  # 已经是完整代码
        code = stock_code[:6]
        if code.startswith(('60', '68')):
            return f"{code}.SH"
        elif code.startswith(('00', '30')):
            return f"{code}.SZ"
        else:
            return f"{code}.BJ"

    @staticmethod
    def _to_em_code(stock_code: str) -> str:
        """xtquant 格式 → 东方财富6位纯代码"""
        if '.' in stock_code:
            return stock_code.split('.')[0]
        return stock_code[:6]

    # ─── 买入 ──────────────────────────────────────────

    def buy(self, stock_code, price, volume):
        """买入股票（先走 Account 基类的资金检查，再调东方财富下单）"""
        if self.cash < price * volume:
            logger.warning(f"资金不足: 需要{price * volume:.2f} 可用{self.cash:.2f}")
            return False

        if not self._live_trading:
            # 模拟模式
            logger.info(f"[模拟] 买入 {stock_code} price={price} volume={volume}")
            self.update_account(stock_code, volume, price)
            return True

        em_code = self._to_em_code(stock_code)
        try:
            result = self._api.buy(em_code, price=price, amount=volume)
            if result.get('success'):
                logger.info(f"买入委托: {stock_code} {price}×{volume}")
                return True
            else:
                logger.error(f"买入失败: {stock_code} {result.get('message', '')}")
                return False
        except Exception as e:
            logger.error(f"买入异常: {stock_code} {e}", exc_info=True)
            return False

    # ─── 卖出 ──────────────────────────────────────────

    def sell(self, stock_code, price, volume):
        """卖出股票"""
        pos = self._positions.get(stock_code)
        if not pos or pos.quantity < volume:
            logger.warning(f"持仓不足: {stock_code} 持有{pos.quantity if pos else 0} 需要{volume}")
            return False

        if not self._live_trading:
            logger.info(f"[模拟] 卖出 {stock_code} price={price} volume={volume}")
            self.update_account(stock_code, -volume, price)
            self._total_cash += price * volume
            return True

        em_code = self._to_em_code(stock_code)
        try:
            result = self._api.sell(em_code, price=price, amount=volume)
            if result.get('success'):
                logger.info(f"卖出委托: {stock_code} {price}×{volume}")
                return True
            else:
                logger.error(f"卖出失败: {stock_code} {result.get('message', '')}")
                return False
        except Exception as e:
            logger.error(f"卖出异常: {stock_code} {e}", exc_info=True)
            return False

    # ─── 一键清仓（force_real）──────────────────────────

    def sell_all(self, stock_code):
        """卖出指定股票全部可用仓位（真实下单，不受 live_trading 限制）"""
        # 先从东方财富同步最新持仓
        self._sync_balance()
        pos = self._positions.get(stock_code)
        if not pos or pos.quantity <= 0:
            logger.warning(f"无持仓或可用数量为0: {stock_code}")
            return None

        em_code = self._to_em_code(stock_code)
        try:
            # 使用市价五档即成剩撤卖出
            result = self._api.sell(em_code, price=0, amount=pos.quantity)
            if result.get('success'):
                logger.info(f"清仓委托: {stock_code} 数量={pos.quantity}")
                return True
            else:
                logger.error(f"清仓失败: {stock_code} {result.get('message', '')}")
                return None
        except Exception as e:
            logger.error(f"清仓异常: {stock_code} {e}", exc_info=True)
            return None

    # ─── 撤单 ──────────────────────────────────────────

    def cancel_order(self, entrust_no):
        """撤销委托"""
        try:
            result = self._api.cancel_entrust(str(entrust_no))
            return result
        except Exception as e:
            logger.error(f"撤单失败: {entrust_no} {e}")
            return None

    # ─── 查询 ──────────────────────────────────────────

    def get_today_orders(self):
        """获取当日委托"""
        try:
            return self._api.get_today_entrusts()
        except Exception as e:
            logger.error(f"查询委托失败: {e}")
            return []

    def get_today_deals(self):
        """获取当日成交"""
        try:
            return self._api.get_today_deals()
        except Exception as e:
            logger.error(f"查询成交失败: {e}")
            return []

    # ─── 登出 ──────────────────────────────────────────

    def logout(self):
        """退出登录"""
        try:
            self._api.logout()
        except Exception:
            pass
