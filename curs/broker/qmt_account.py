import logging
import time
from typing import List
from xml.dom.pulldom import parseString

from xtquant import xtconstant, xtdata
from xtquant.xttrader import XtQuantTrader, XtQuantTraderCallback
from xtquant.xttype import StockAccount, XtPosition

logger = logging.getLogger(__name__)
#https://dict.thinktrader.net/nativeApi/xttrader.html?id=e2M5nZ#%E6%88%90%E4%BA%A4xttrade
class MyXtQuantTraderCallback(XtQuantTraderCallback):
    def on_connected(self):
        logger.info("qmt on_connected")

    def on_smt_appointment_async_response(self, response):
        logger.info(f"qmt on_smt_appointment_async_response: {vars(response)}")

    def on_cancel_order_stock_async_response(self, response):
        logger.info(f"qmt on_cancel_order_stock_async_response: {vars(response)}")

    def on_disconnected(self):
        """
        连接断开
        :return:
        """
        logger.info(f"qmt on_disconnected")

    def on_stock_order(self, order):
        """
        委托回报推送
        :param order: XtOrder对象
        :return:
        """
        logger.info(f"qmt on_stock_order: {vars(order)}")

    def on_stock_asset(self, asset):
        """
        资金变动推送
        :param asset: XtAsset对象
        :return:
        """
        logger.info(f"qmt on_stock_asset: {vars(asset)}")

    def on_stock_trade(self, trade):
        """
        成交变动推送
        :param trade: XtTrade对象
        :return:
        """
        logger.info(f"qmt on_stock_trade: {vars(trade)}")

    def on_stock_position(self, position):
        """
        持仓变动推送
        :param position: XtPosition对象
        :return:
        """
        logger.info(f"qmt on_stock_position: {vars(position)}")

    def on_order_error(self, order_error):
        """
        委托失败推送
        :param order_error:XtOrderError 对象
        :return:
        """
        logger.info(f"qmt on_order_error: {vars(order_error)}")

    def on_cancel_error(self, cancel_error):
        """
        撤单失败推送
        :param cancel_error: XtCancelError 对象
        :return:
        """
        logger.info(f"qmt on_cancel_error: {vars(cancel_error)}")

    def on_order_stock_async_response(self, response):
        """
        异步下单回报推送
        :param response: XtOrderResponse 对象
        :return:
        """
        logger.info(f"qmt on_order_stock_async_response: {vars(response)}")

    def on_account_status(self, status):
        """
        :param response: XtAccountStatus 对象
        :return:
        """
        logger.info(f"qmt on_account_status: {vars(status)}")


class QmtStockAccount():
    def __init__(self, path, account_id, trader_name, session_id=None) -> None:
        if not session_id:
            session_id = int(time.time())
        self.trader_name = trader_name
        logger.info(f"path: {path}, account: {account_id}, trader_name: {trader_name}, session: {session_id}")

        self.xt_trader = XtQuantTrader(path=path, session=session_id)

        # StockAccount可以用第二个参数指定账号类型，如沪港通传'HUGANGTONG'，深港通传'SHENGANGTONG'
        self.account = StockAccount(account_id=account_id, account_type="STOCK")

        # 创建交易回调类对象，并声明接收回调
        callback = MyXtQuantTraderCallback()
        self.xt_trader.register_callback(callback)

        # 启动交易线程
        self.xt_trader.start()

        # 建立交易连接，返回0表示连接成功
        connect_result = self.xt_trader.connect()
        if connect_result != 0:
            logger.error(f"qmt trader 连接失败: {connect_result}")
            # raise QmtError(f"qmt trader 连接失败: {connect_result}")
        logger.info("qmt trader 建立交易连接成功！")

        # 对交易回调进行订阅，订阅后可以收到交易主推，返回0表示订阅成功
        subscribe_result = self.xt_trader.subscribe(self.account)

        if subscribe_result != 0:
            logger.error(f"账号订阅失败: {subscribe_result}")
            # raise QmtError(f"账号订阅失败: {subscribe_result}")
        logger.info("账号订阅成功！")

    def get_positions(self):
        positions: List[XtPosition] = self.xt_trader.query_stock_positions(self.account)
        return positions

    def get_current_position(self, entity_id, create_if_not_exist=False):
        # stock_code = _to_qmt_code(entity_id=entity_id)
        stock_code = entity_id
        # 根据股票代码查询对应持仓
        return self.xt_trader.query_stock_position(self.account, stock_code)

    def get_current_account(self):
        asset = self.xt_trader.query_stock_asset(self.account)
        return asset

    def order_by_amount(self, entity_id, order_price, order_timestamp, order_type, order_amount):
        # stock_code = _to_qmt_code(entity_id=entity_id)
        stock_code = entity_id
        fix_result_order_id = self.xt_trader.order_stock(
            account=self.account,
            stock_code=stock_code,
            # order_type=_to_qmt_order_type(order_type=order_type),
            order_type=order_type,
            order_volume=order_amount,
            price_type=xtconstant.FIX_PRICE,
            price=order_price,
            strategy_name=self.trader_name,
            order_remark="order from cly",
        )
        logger.info(f"order result id: {fix_result_order_id}")

    # def on_trading_signals(self, trading_signals: List[TradingSignal]):
    #     for trading_signal in trading_signals:
    #         try:
    #             self.handle_trading_signal(trading_signal)
    #         except Exception as e:
    #             logger.exception(e)
    #             self.on_trading_error(timestamp=trading_signal.happen_timestamp, error=e)

    # def handle_trading_signal(self, trading_signal: TradingSignal):
    #     entity_id = trading_signal.entity_id
    #     happen_timestamp = trading_signal.happen_timestamp
    #     order_type = trading_signal_type_to_order_type(trading_signal.trading_signal_type)
    #     trading_level = trading_signal.trading_level.value
    #     # askPrice	多档委卖价
    #     # bidPrice	多档委买价
    #     # askVol	多档委卖量
    #     # bidVol	多档委买量
    #     if now_pd_timestamp() > to_pd_timestamp(trading_signal.due_timestamp):
    #         logger.warning(
    #             f"the signal is expired, now {now_pd_timestamp()} is after due time: {trading_signal.due_timestamp}"
    #         )
    #         return
    #     quote = xtdata.get_l2_quote(stock_code=_to_qmt_code(entity_id=entity_id), start_time=happen_timestamp)
    #     if order_type == OrderType.order_long:
    #         price = quote["askPrice"]
    #     elif order_type == OrderType.order_close_long:
    #         price = quote["bidPrice"]
    #     else:
    #         assert False
    #     self.order_by_amount(
    #         entity_id=entity_id,
    #         order_price=price,
    #         order_timestamp=happen_timestamp,
    #         order_type=order_type,
    #         order_amount=trading_signal.order_amount,
    #     )

    def on_trading_open(self, timestamp):
        pass

    def on_trading_close(self, timestamp):
        pass

    def on_trading_finish(self, timestamp):
        pass

    def on_trading_error(self, timestamp, error):
        pass
    def sell_all(self, stock_code):
        print(stock_code)
        print(self.account)
        position = self.xt_trader.query_stock_position(self.account,stock_code)
        print(position)
        fix_result_order_id = self.xt_trader.order_stock(
                account=self.account,
                stock_code=stock_code,
                order_type=xtconstant.STOCK_SELL,
                order_volume=int(position.can_use_volume),
                price_type=xtconstant.MARKET_SH_CONVERT_5_CANCEL,
                price=0,
                strategy_name=self.trader_name,
                order_remark="order from cly",
        )
        logger.info(f"order result id: {fix_result_order_id}")

    def sell_market_convert_5_cancel(self, stock_code,volume):
        fix_result_order_id = self.xt_trader.order_stock(
                account=self.account,
                stock_code=stock_code,
                order_type=xtconstant.STOCK_SELL,
                order_volume=int(volume),
                price_type=xtconstant.MARKET_SH_CONVERT_5_CANCEL,
                price=0,
                strategy_name=self.trader_name,
                order_remark="order from cly",
        )
        logger.info(f"order result id: {fix_result_order_id}")

    def sell_latest_price(self, stock_code,volume):
        fix_result_order_id = self.xt_trader.order_stock(
                account=self.account,
                stock_code=stock_code,
                order_type=xtconstant.STOCK_SELL,
                order_volume=int(volume),
                price_type=xtconstant.LATEST_PRICE,
                price=0,
                strategy_name=self.trader_name,
                order_remark="order from cly",
        )
        logger.info(f"order result id: {fix_result_order_id}")

    def sell_fix_price(self, stock_code,volume,price):
        fix_result_order_id = self.xt_trader.order_stock(
                account=self.account,
                stock_code=stock_code,
                order_type=xtconstant.STOCK_SELL,
                order_volume=int(volume),
                price_type=xtconstant.FIX_PRICE,
                price=price,
                strategy_name=self.trader_name,
                order_remark="order from cly",
        )
        logger.info(f"order result id: {fix_result_order_id}")

    def buy_latest_price(self, stock_code,volume):

        fix_result_order_id = self.xt_trader.order_stock(
            account=self.account,
            stock_code=stock_code,
            order_type=xtconstant.STOCK_BUY,
            order_volume=int(volume),
            price_type=xtconstant.LATEST_PRICE,
            price=0,
            strategy_name=self.trader_name,
            order_remark="order from cly",
        )
        logger.info(f"order result id: {fix_result_order_id}")
        return fix_result_order_id
    
    def buy_fix_price(self, stock_code,volume,price):

        fix_result_order_id = self.xt_trader.order_stock(
            account=self.account,
            stock_code=stock_code,
            order_type=xtconstant.STOCK_BUY,
            order_volume=int(volume),
            price_type=xtconstant.FIX_PRICE,
            price=price,
            strategy_name=self.trader_name,
            order_remark="order from cly",
        )
        logger.info(f"order result id: {fix_result_order_id}")
        return fix_result_order_id

    def query_orders(self):
        orders = self.xt_trader.query_stock_orders(self.account, False)
        return orders
    def query_trades(self):
        trades = self.xt_trader.query_stock_trades(self.account)
        return trades
    def adjust_position(self,buy_stocks):
        positions = self.get_positions()
        for position in positions:
            if position.stock_code not in buy_stocks:
                log.info("stock [%s] in position is not buyable" %(position.stock_code))
                self.sell_all(position.stock_code)
            else:
                log.info("stock [%s] is already in position" %(position.stock_code))

        # 根据股票数量分仓
        # 此处只根据可用金额平均分配购买，不能保证每个仓位平均分配
        position_count = len(positions)
        buy_stock_count = 4
        if buy_stock_count > position_count:
            asset = self.get_current_account()
            value = asset.cash / (buy_stock_count - position_count)

            for stock in buy_stocks:
                if self.buy(stock, value):
                    pass

  
            
if __name__ == "__main__":
    account = QmtStockAccount(path=r"E:\qmt\userdata_mini", account_id="88888888",trader_name="curs")
    posistions = account.get_positions()
        #     :param account_id: 资金账号
        # :param stock_code: 证券代码, 例如"600000.SH"
        # :param volume: 持仓数量,股票以'股'为单位, 债券以'张'为单位
        # :param can_use_volume: 可用数量, 股票以'股'为单位, 债券以'张'为单位
        # :param open_price: 开仓价
        # :param market_value: 市值
        # :param frozen_volume: 冻结数量
        # :param on_road_volume: 在途股份
        # :param yesterday_volume: 昨夜拥股

    for position in posistions:
        print(position.account_id, position.stock_code, position.volume, position.can_use_volume, position.open_price, position.market_value, position.frozen_volume, position.on_road_volume, position.yesterday_volume)
    asset = account.get_current_account()
    # account_type	int	账号类型，参见数据字典
    # account_id	str	资金账号
    # cash	float	可用金额
    # frozen_cash	float	冻结金额
    # market_value	float	持仓市值
    # total_asset	float	总资产
    print(asset.account_id, asset.account_type, asset.cash, asset.frozen_cash, asset.market_value, asset.total_asset)
    #
    # account.sell_market_convert_5_cancel("002681.SZ",100)
    account.buy_latest_price("002195.SZ",100)
    