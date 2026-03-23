# coding: utf-8
from curs.log_handler.logger import logger
from curs.cursglobal import *
from curs.api import *
from curs.broker.qmt_account import QmtStockAccount,Position
from curs.database import get_db_manager
from curs.broker.order_tracker import OrderTracker, OrderCallback
from curs.broker.profit_stats import ProfitStats
import time
import json
import os
import random
from datetime import datetime, timedelta
import math
import threading

# 初始化策略
def init(context):
    """初始化涨停板策略"""
    logger.info("初始化涨停板策略")
    # 初始化账户
    qmt_path = CursGlobal.get_instance().config["base"]["accounts"]["qmt_path"]
    account_id = CursGlobal.get_instance().config["base"]["accounts"]["qmt_account_id"]
    trader_name = CursGlobal.get_instance().config["base"]["accounts"]["qmt_trader_name"]
    context.account = QmtStockAccount(path=qmt_path,account_id=account_id,trader_name=trader_name, total_cash=100000)  # 初始资金为10万元
    
    # 初始化订单跟踪器 (最大等待30秒超时，5秒检查间隔)
    context.order_tracker = OrderTracker(max_wait_seconds=30, check_interval=5)
    context.order_tracker.start()
    
    # 初始化盈利统计
    context.profit_stats = ProfitStats(data_dir=os.path.join(os.getcwd(), 'data/strategy_records'))
    
    # 设置订单回调
    if hasattr(context.account, 'xt_trader'):
        context.order_callback = OrderCallback(
            context.order_tracker, 
            context.account.xt_trader, 
            context.account.account
        )
    
    # 存储每只股票的上次挂单量
    context.last_order_volumes = {}
    # 存储交易记录（包含峰值价格）
    context.trade_records = {}
    #pre ticksFalse
    context.pre_ticks = {}
    # 监控间隔时间（秒）
    context.monitor_interval = 3
    # 每日交易记录
    context.daily_trades = []
    # 成功交易计数
    context.success_count = 0
    # 总交易计数
    context.total_count = 0
    # 历史交易记录
    context.historical_trades = []
    # 数据存储路径
    context.data_dir = os.path.join(os.getcwd(), 'data')
    os.makedirs(context.data_dir, exist_ok=True)
    context.data_file = os.path.join(context.data_dir, 'strategy_records/limit_up_strategy_trades.json')
    # 加载历史数据
    load_historical_trades(context)
    # 获取股票基本信息
    en_list = get_entity_list()
    map_info = {}
    for en in en_list:
        map_info[en["id"]] = en
    context.stock_base_info = map_info
    # 存储每日已触发信号的股票
    context.daily_signaled_stocks = set()
    context.current_time = None
    # 从数据库获取昨日涨停股票列表
    context.pre_limit_up_stocks = set()
    context.open_time = datetime.strptime("09:35:00", "%H:%M:%S").time()
    context.close_time = datetime.strptime("14:00:00", "%H:%M:%S").time()

    # 获取昨日日期
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

    # 从数据库获取昨日涨停股票
    db_manager = get_db_manager()
    zt_stocks = db_manager.get_zt_stocks_by_date(yesterday)
    context.pre_limit_up_stocks = set(zt_stocks)

    logger.info(f"成功从数据库加载昨日涨停股列表，共{len(context.pre_limit_up_stocks)}只")

    # 从数据库获取热门股票池
    context.hot_stocks = set()
    hot_stocks = db_manager.get_hot_stocks_from_pool('hot')
    context.hot_stocks = set(hot_stocks)

    logger.info(f"成功从数据库加载热门股票池，共{len(context.hot_stocks)}只")
    
    
def load_stocks_fromfile(context, file_name):
    """加载昨日的热点股列表"""
    #清空昨日涨停股列表
    context.hot_stocks.clear()
    file_path = context.data_dir + file_name
    try:
        with open(file_path, 'r') as f:
            for line in f:
                context.hot_stocks.add(line.strip())
        logger.info(f"成功加载昨日热点股列表，共{len(context.hot_stocks)}只")
    except FileNotFoundError:
        print(f"文件 {file_path} 未找到，请检查路径和文件名。")
    except Exception as e:
        print(f"加载文件时出现错误: {e}")
        
def load_historical_trades(context):
    """加载历史交易数据"""
    if os.path.exists(context.data_file):
        try:
            with open(context.data_file, 'r', encoding='utf-8') as f:
                context.historical_trades = json.load(f)
            logger.info(f"成功加载历史交易记录，共{len(context.historical_trades)}条")
        except Exception as e:
            logger.error(f"加载历史交易记录失败: {str(e)}")
            context.historical_trades = []
    else:
        context.historical_trades = []

def before_trading(context):
    """盘前初始化"""
    try:
        _before_trading_inner(context)
    except Exception as e:
        logger.error(f"盘前初始化异常: {e}", exc_info=True)


def _before_trading_inner(context):
    """盘前初始化内部实现"""
    # 清空挂单量记录
    context.last_order_volumes.clear()
    # 清空每日信号记录
    context.daily_signaled_stocks.clear()
    # 清空交易记录
    context.trade_records.clear()
    
    # 重新启动订单跟踪器
    if hasattr(context, 'order_tracker'):
        context.order_tracker.start()
    
    # 计算并记录历史成功率
    total_trades = len(context.historical_trades) + context.total_count
    if total_trades > 0:
        total_success = sum(1 for trade in context.historical_trades if trade['success']) + context.success_count
        success_rate = total_success / total_trades * 100
        logger.info(f"历史交易成功率：{success_rate:.2f}% （成功：{total_success}，总交易：{total_trades}）")
    
        
    context.daily_trades = []
    context.success_count = 0
    context.total_count = 0
    
    logger.info("涨停板策略初始化完成")
# 新增卖出处理函数
def sell_strategy(context,stock_code,tick):
    """次日卖出策略组合"""
    try:
        _sell_strategy_inner(context, stock_code, tick)
    except Exception as e:
        logger.error(f"卖出策略异常: stock_code={stock_code}, {e}", exc_info=True)


def _sell_strategy_inner(context, stock_code, tick):
    """卖出策略内部实现"""
    # 策略2：10:00-10:30卖出窗口        
    current_time = context.current_time

    if not (datetime.time(10, 0) <= current_time.time() <= datetime.time(10, 30)):
        return
    #如果股票当天涨停
    position = context.account.get_position(stock_code)
    if position is None:
        return

    if position.quantity == 0:
        return
    
    # 获取涨停价
    upper_limit = context.stock_base_info[stock_code]['limit_up_price']
    #已经涨停过的股票不再买入，针对涨停之后开板的股票
    bid_prices = tick.get('bidPrice', [])
    #如果涨停，继续持有
    if upper_limit in bid_prices:
        return
    # 获取实时行情
    buy_price = position.avg_cost
    current_price = tick['lastPrice']
    high_price = tick['high']

    
    # 策略1：动态止盈止损
    max_peak = context.trade_records[stock_code]['peak_price']  # 记录当日最高价
    if current_price > max_peak:
        max_peak = current_price
        context.trade_records[stock_code]['peak_price'] = max_peak
        
    # 回落2%止损
    if current_price < max_peak * 0.98:
        order_volume = position.quantity
        if context.account.sell_fix_price(stock_code,order_volume, current_price):
            # 计算盈利
            buy_price = context.trade_records[stock_code].get('buy_price', current_price)
            profit_pct = (current_price - buy_price) / buy_price * 100
            
            context.profit_stats.record_sell(stock_code, current_price, order_volume)
            
            # 保存到数据库
            try:
                db_manager = get_db_manager()
                db_manager.update_profit_record_sold(
                    stock_code=stock_code,
                    sell_price=current_price,
                    sell_time=datetime.now(),
                    sell_volume=order_volume,
                    profit_pct=profit_pct
                )
            except Exception as e:
                logger.error(f"更新数据库盈利记录失败: {e}")
            
            log_sale('dynamic_stop', stock_code, order_volume)
    
    
    
    # 策略3：尾盘强制清仓
    if current_time.time() >= datetime.time(14, 55):
        if context.account.sell_fix_price(stock_code, current_price, position.quantity):
            # 计算盈利
            buy_price = context.trade_records[stock_code].get('buy_price', current_price)
            profit_pct = (current_price - buy_price) / buy_price * 100
            
            context.profit_stats.record_sell(stock_code, current_price, position.quantity)
            
            # 保存到数据库
            try:
                db_manager = get_db_manager()
                db_manager.update_profit_record_sold(
                    stock_code=stock_code,
                    sell_price=current_price,
                    sell_time=datetime.now(),
                    sell_volume=position.quantity,
                    profit_pct=profit_pct
                )
            except Exception as e:
                logger.error(f"更新数据库盈利记录失败: {e}")
            
            log_sale('force_close', stock_code, position.quantity)

def log_sale(strategy, code, vol):
    logger.info(f"[{strategy}] 卖出 {code} 数量 {vol} 时间 {datetime.now()}")

def handle_tick(context, ticks):
    """处理tick数据"""
    try:
        _handle_tick_inner(context, ticks)
    except Exception as e:
        logger.error(f"处理tick异常: {e}", exc_info=True)


def _handle_tick_inner(context, ticks):
    """处理tick数据内部实现"""
    # 全局风险控制 --------------------------
    # # 1. 单日最大回撤控制
    # if context.account.total_assets < context.account.init_assets * 0.98:
    #     logger.warning("触发单日最大回撤2%，停止交易")
    #     close_all_positions(context)
    #     return
    
    # # 2. 板块风险监控
    # current_industry = get_stock_industry(stock_code)
    # if context.industry_risk[current_industry] > 0.05:  # 板块内5%个股跌停
    #     logger.warning(f"{current_industry}板块出现风险，禁止交易")
    #     return
        #     # 新增多维买入条件验证 --------------------------
        # # 1. 封单强度验证（封单金额/流通市值）
        # circulation_mv = context.stock_base_info[stock_code].get('circ_mv', 1e8)  # 获取流通市值
        # upper_limit = context.stock_base_info[stock_code]['limit_up_price']
        # limit_order_vol = ask_volumes[ask_prices.index(upper_limit)]  # 涨停价挂单量
        # limit_order_amount = limit_order_vol * upper_limit  # 封单金额
        # seal_strength_ratio = limit_order_amount / circulation_mv
        
        # # 2. 挂单变化速率验证（单位：手/秒）
        # pre_vol = context.last_order_volumes.get(stock_code, limit_order_vol)
        # vol_change_speed = (pre_vol - limit_order_vol) / context.monitor_interval
        
        # # 3. 市场情绪验证（全市场涨停股数量）
        # all_zt_count = sum(1 for code in ticks if ticks[code]['lastPrice'] >= ticks[code]['pre_close'] * 1.099)
        
        # # 综合买入条件（原条件+新条件）
        # if (current_volume <= last_volume * 0.75 and 
        #     seal_strength_ratio > 0.005 and  # 封单强度>0.5%流通市值
        #     vol_change_speed > 500 and       # 挂单减少速度>500手/秒
        #     all_zt_count > 30):               # 全市场涨停股>30只
        #     buy_at_limit_up(context, stock_code, upper_limit)
        #     context.daily_signaled_stocks.add(stock_code)
    
    for stock_code, tick in ticks.items():
#         'time' =
# 1739170800000
        # unix time to datetime,精确到毫秒
        current_time = datetime.fromtimestamp(tick.get('time', 0) / 1000)
        context.current_time= current_time
        current_time_of_day = current_time.time()
        
        # 更新价格到订单跟踪器和盈利统计
        current_price = tick.get('lastPrice', 0)
        if current_price > 0:
            context.order_tracker.update_price(stock_code, current_price)
            context.profit_stats.update_price(stock_code, current_price)
        
        # 检查待成交订单状态
        pending_orders = context.order_tracker.get_pending_orders()
        for order in pending_orders:
            if order.stock_code == stock_code:
                # 检查持仓是否已有该股票（说明已成交）
                position = context.account.get_position(stock_code)
                if position and position.quantity > 0:
                    # 成交了！
                    context.order_tracker.update_order_status(
                        order.order_id,
                        "FULL",
                        filled_volume=position.quantity,
                        avg_price=position.avg_price
                    )
                    context.profit_stats.record_filled(
                        stock_code,
                        filled_price=position.avg_price,
                        filled_volume=position.quantity
                    )
                    
                    # 保存到数据库
                    try:
                        db_manager = get_db_manager()
                        db_manager.update_profit_record_filled(
                            stock_code=stock_code,
                            filled_price=position.avg_price,
                            filled_time=datetime.now(),
                            filled_volume=position.quantity
                        )
                    except Exception as e:
                        logger.error(f"更新数据库盈利记录失败: {e}")
                else:
                    # 检查是否超时未成交（超过60秒）
                    wait_seconds = (current_time - order.order_time).total_seconds()
                    if wait_seconds > 60:
                        # 超时未成交，标记为失败（交易机会已丧失）
                        context.order_tracker.update_order_status(
                            order.order_id,
                            "TIMEOUT",
                            filled_volume=0,
                            avg_price=0
                        )
                        logger.warning(f"订单超时未成交，已放弃: {order.order_id} - {stock_code}")
                    
                    logger.info(f"检测到订单成交: {stock_code} - 数量: {position.quantity}")
        
        # 过滤时间段:9:30-14:57
        if not (context.open_time <= current_time_of_day <= context.close_time):
             continue
        if context.pre_limit_up_stocks and stock_code in context.pre_limit_up_stocks:
            # logger.info(f"昨日涨停股票：{stock_code}，不再买入")
            continue
        #update pre_ticks
        context.pre_ticks[stock_code] = tick
        # 过滤ST股票 name中含有ST或st
        stock_name = context.stock_base_info[stock_code].get('name', '')
        if 'ST' in stock_name or 'st' in stock_name:
            continue

        # 过滤昨日涨停的股票
        # if tick.get('pre_close', 0) == tick.get('limit_up_price', 0):
        #     continue
            
        # 过滤已经触发过信号的股票
        if stock_code in context.daily_signaled_stocks:
            continue
        
        if stock_code not in context.hot_stocks:
            continue
            
        # 获取5档行情
        ask_prices = tick.get('askPrice', [])
        ask_volumes = tick.get('askVol', [])
        
        # 获取涨停价
        upper_limit = context.stock_base_info[stock_code]['limit_up_price']
        #已经涨停过的股票不再买入，针对涨停之后开板的股票
        bid_prices = tick.get('bidPrice', [])
        if upper_limit in bid_prices:
            context.daily_signaled_stocks.add(stock_code)
        # 检查5档行情中是否有涨停价
        if upper_limit in ask_prices:
            # 获取涨停价对应的卖单量
            limit_up_index = ask_prices.index(upper_limit)
            current_volume = ask_volumes[limit_up_index] if limit_up_index < len(ask_volumes) else 0
            if current_volume == 0:
                continue
            # 获取上次挂单量
            last_volume = context.last_order_volumes.get(stock_code, current_volume)
                                                    
            # 判断挂单量是否减少0.4
            if current_volume <= last_volume * 0.6:
                # 触发买入
                buy_at_limit_up(context, stock_code, upper_limit)
                # 标记该股票已触发信号
                context.daily_signaled_stocks.add(stock_code)

                
            # 更新挂单量 取最大值
            context.last_order_volumes[stock_code] = current_volume
        #已经涨停，判断是否排版
        if upper_limit in bid_prices:
            # 获取上次挂单量
            current_volume = 0
            last_volume = context.last_order_volumes.get(stock_code, current_volume)
            if last_volume > 0:
                logger.info(f"触发排版买入:{stock_code}")
                # 触发排版买入
                buy_at_limit_up(context, stock_code, upper_limit)
                
                context.last_order_volumes[stock_code] = 0


def buy_at_limit_up(context, stock_code, price):
    """以涨停价买入"""
    try:
        _buy_at_limit_up_inner(context, stock_code, price)
    except Exception as e:
        logger.error(f"买入策略异常: stock_code={stock_code}, price={price}, {e}", exc_info=True)


def _buy_at_limit_up_inner(context, stock_code, price):
    """以涨停价买入内部实现"""
    # return
    if context.pre_limit_up_stocks and stock_code in context.pre_limit_up_stocks:
        # logger.info(f"昨日涨停股票：{stock_code}，不再买入")
        return
    # 获取账户信息
    account = context.account

    # 计算可买数量
    available_cash = 10000
    buy_volume = int(available_cash / price / 100 +1) * 100  # 按手数买入

    if buy_volume > 0:
        # 生成订单ID
        order_id = str(random.randint(1000000, 9999999))

        # 先保存买入信号到数据库（不管下单成功与否都要记录信号）
        db_manager = get_db_manager()
        try:
            signal_saved = db_manager.save_strategy_signal(
                strategy_name='limit_up_strategy',
                stock_code=stock_code,
                signal_type='BUY',
                price=price,
                volume=buy_volume,
                order_id=order_id,
                status='PENDING'
            )
            
            if signal_saved:
                logger.info(f"策略信号已保存到数据库: {stock_code} - BUY - {price}")
            else:
                logger.warning(f"策略信号保存返回失败: {stock_code}, 将重试")
                # 重试一次
                signal_saved = db_manager.save_strategy_signal(
                    strategy_name='limit_up_strategy',
                    stock_code=stock_code,
                    signal_type='BUY',
                    price=price,
                    volume=buy_volume,
                    order_id=order_id,
                    status='PENDING'
                )
        except Exception as e:
            logger.error(f"保存策略信号到数据库异常: {e}, stock_code={stock_code}")
            signal_saved = False

        # 注册订单到跟踪器
        context.order_tracker.register_order(
            stock_code=stock_code,
            order_id=order_id,
            volume=buy_volume,
            price=price,
            order_type="BUY"
        )

        # 记录买入到盈利统计（内存）
        context.profit_stats.record_buy(
            stock_code=stock_code,
            order_id=order_id,
            price=price,
            volume=buy_volume,
            buy_time=context.current_time
        )

        # 初始化交易记录（用于追踪峰值价格）
        if stock_code not in context.trade_records:
            context.trade_records[stock_code] = {
                'peak_price': price,
                'buy_price': price,
                'buy_time': context.current_time
            }

        # 下单
        order_success = False
        try:
            order_success = account.buy_fix_price(stock_code,buy_volume, price)
        except Exception as e:
            logger.error(f"下单异常: {stock_code}, {e}")
        
        if order_success:
            logger.info(f"涨停板买入：{stock_code}，价格：{price}，数量：{buy_volume}, 时间：{context.current_time}")

            # 更新信号状态为已执行
            try:
                db_manager.update_signal_status_by_order_id(order_id, 'EXECUTED')
            except Exception as e:
                logger.error(f"更新信号状态为EXECUTED失败: {e}")
            
            # 保存盈利记录到数据库
            try:
                db_manager.save_profit_record(
                    stock_code=stock_code,
                    order_id=order_id,
                    buy_price=price,
                    buy_time=context.current_time
                )
            except Exception as e:
                logger.error(f"保存盈利记录到数据库失败: {e}")

            # 记录交易
            trade_record = {
                'date': time.strftime("%Y-%m-%d %H:%M:%S"),
                'stock': stock_code,
                'price': price,
                'volume': buy_volume,
                'order_id': order_id
            }
            context.daily_trades.append(trade_record)
            context.total_count += 1
        else:
            logger.warning(f"买入下单返回失败：{stock_code}，价格：{price}，数量：{buy_volume}")
            # 更新信号状态为取消（但信号本身已保存）
            try:
                db_manager.update_signal_status_by_order_id(order_id, 'CANCELLED')
            except Exception as e:
                logger.error(f"更新信号状态为CANCELLED失败: {e}")

def save_historical_trades(context):
    """保存历史交易数据"""
    # 保存并重置每日记录
    if context.daily_trades:
        # 标记交易是否成功
        for trade in context.daily_trades:
            current_price = context.pre_ticks[trade["stock"]]['lastPrice']
            # trade['success'] = current_price >= trade['price']
            trade['success'] = math.isclose(current_price, trade['price'])
            if not trade['success']:
                logger.error(f"交易失败：{trade['stock']}，trade price：{trade['price']}，current_price：{current_price}")
        context.historical_trades.extend(context.daily_trades)
    try:
        with open(context.data_file, 'w', encoding='utf-8') as f:
            json.dump(context.historical_trades, f, ensure_ascii=False, indent=2)
        logger.info("成功保存历史交易记录")
    except Exception as e:
        logger.error(f"保存历史交易记录失败: {str(e)}")

def check_trade_outcomes(context):
    """检查交易结果并更新成功率"""
    account = context.account
    for trade in context.daily_trades:
        # 获取当前价格
        position = account.positions.get(trade['stock'], Position())
        current_price = position._last_price if position.quantity > 0 else 0
        trade['current_price'] = current_price
        
        # 如果当前价格大于等于买入价，视为成功
        if current_price >= trade['price']:
            context.success_count += 1

def after_trading(context):
    """盘后处理"""
    try:
        _after_trading_inner(context)
    except Exception as e:
        logger.error(f"盘后处理异常: {e}", exc_info=True)


def _after_trading_inner(context):
    """盘后处理内部实现"""
    # 停止订单跟踪器
    if hasattr(context, 'order_tracker'):
        context.order_tracker.stop()
    
    # 检查当日交易结果
    check_trade_outcomes(context)
    save_historical_trades(context)
    context.account.save_daily_account_info('limit_up_strategy')
    logger.info(f"当日交易记录：{context.daily_trades}")
    
    # 输出盈利统计报告
    if hasattr(context, 'profit_stats'):
        report = context.profit_stats.get_summary_report()
        logger.info(f"\n{report}")
