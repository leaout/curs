# coding: utf-8
"""
东方财富证券 Broker 适配层
封装 eastmoney_trade_api.py，实现标准账户与下单接口
"""

import logging
from types import SimpleNamespace

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

        masked_account = f"****{account_no[-4:]}" if len(account_no) >= 4 else "****"
        logger.info(f"东方财富账户登录成功: {masked_account}")

    # ─── live_trading 属性 ───────────────────────────────

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
            self._positions.clear()
            for p in api_positions:
                code = p['stock_code']
                # 东方财富返回的是6位纯代码，需要加上交易所后缀
                code_with_suffix = self._to_broker_code(code)
                pos = self.positions.get(code_with_suffix)
                if pos is None:
                    pos = Position()
                    self.positions[code_with_suffix] = pos
                pos.quantity = p['current_amount']
                pos.avg_price = p['cost_price']
                pos._last_price = p['last_price']
                pos._non_closable = max(0, p['current_amount'] - p['enable_amount'])

            logger.debug(f"资金同步: 可用{balance['enable_balance']:.2f} 市值{balance['market_value']:.2f}")
        except Exception as e:
            logger.exception(f"资金同步失败: {e}")
            raise RuntimeError(f"东方财富资金同步失败: {e}") from e

    def get_positions(self):
        """获取标准字段表示的实时持仓列表。"""
        self._sync_balance()
        result = []
        for stock_code, pos in self._positions.items():
            can_use_volume = max(0, pos.quantity - pos._non_closable)
            result.append(SimpleNamespace(
                account_id=self.account_no,
                stock_code=stock_code,
                volume=pos.quantity,
                can_use_volume=can_use_volume,
                open_price=pos.avg_price,
                market_value=pos.market_value(),
                frozen_volume=0,
                on_road_volume=pos._non_closable,
                yesterday_volume=can_use_volume,
            ))
        return result

    def get_current_account(self):
        """获取标准字段表示的实时账户资产。"""
        self._sync_balance()
        return SimpleNamespace(
            account_id=self.account_no,
            cash=self.cash,
            frozen_cash=self.frozen_cash,
            market_value=self.market_value,
            total_asset=self.cash + self.frozen_cash + self.market_value,
        )

    @staticmethod
    def _to_broker_code(stock_code: str) -> str:
        """
        东方财富6位代码 → 带交易所后缀的内部代码
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
        """带交易所后缀的内部代码 → 东方财富6位纯代码"""
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
        available = max(0, pos.quantity - pos._non_closable) if pos is not None else 0
        if available < volume:
            logger.warning(f"可用持仓不足: {stock_code} 可用{available} 需要{volume}")
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

    def buy_fix_price(self, stock_code, volume, price):
        """按限价买入。"""
        return self.buy(stock_code, price, int(volume))

    def sell_fix_price(self, stock_code, volume, price):
        """按限价卖出。"""
        return self.sell(stock_code, price, int(volume))

    def buy_latest_price(self, stock_code, volume):
        """按东方财富市价参数买入。"""
        return self.buy(stock_code, 0, int(volume))

    def sell_latest_price(self, stock_code, volume):
        """按东方财富市价参数卖出。"""
        return self.sell(stock_code, 0, int(volume))

    # ─── 一键清仓（force_real）──────────────────────────

    def sell_all(self, stock_code):
        """卖出指定股票全部可用仓位（真实下单，不受 live_trading 限制）"""
        # 先从东方财富同步最新持仓
        self._sync_balance()
        pos = self._positions.get(stock_code)
        available = max(0, pos.quantity - pos._non_closable) if pos is not None else 0
        if available <= 0:
            logger.warning(f"无持仓或可用数量为0: {stock_code}")
            return None

        em_code = self._to_em_code(stock_code)
        try:
            # 使用市价五档即成剩撤卖出
            result = self._api.sell(em_code, price=0, amount=available)
            if result.get('success'):
                logger.info(f"清仓委托: {stock_code} 数量={available}")
                return True
            else:
                logger.error(f"清仓失败: {stock_code} {result.get('message', '')}")
                return None
        except Exception as e:
            logger.error(f"清仓异常: {stock_code} {e}", exc_info=True)
            return None

    def liquidate_all_positions(self):
        """清仓全部可用持仓。"""
        results = []
        for position in self.get_positions():
            if position.can_use_volume <= 0:
                continue
            order_id = self.sell_all(position.stock_code)
            if order_id:
                results.append({
                    'stock_code': position.stock_code,
                    'volume': position.can_use_volume,
                    'order_id': order_id,
                })
        return results

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
