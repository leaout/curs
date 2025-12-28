# coding: utf-8
"""
涨停板策略 - 高级版 (T+1策略)
特点：
- 第一天打板买入
- 第二天根据开盘走势智能卖出
- 无需手动干预，完全自动化
"""

from curs.log_handler.logger import logger
from curs.cursglobal import *
from curs.api import *
from curs.broker.qmt_account import QmtStockAccount, Position
from curs.database import get_db_manager
import time
import json
import os
import random
from datetime import datetime, timedelta
import math

# 初始化策略
def init(context):
    """初始化涨停板策略 - 高级版"""
    logger.info("初始化涨停板策略 - 高级版 (T+1)")
    # 初始化账户
    qmt_path = CursGlobal.get_instance().config["base"]["accounts"]["qmt_path"]
    account_id = CursGlobal.get_instance().config["base"]["accounts"]["qmt_account_id"]
    trader_name = CursGlobal.get_instance().config["base"]["accounts"]["qmt_trader_name"]
    context.account = QmtStockAccount(path=qmt_path, account_id=account_id, trader_name=trader_name, total_cash=100000)

    # ===== 交易参数配置 =====
    context.max_single_position = 10000  # 单只股票最大持仓金额
    context.max_total_positions = 5      # 最大持仓股票数量
    context.min_order_volume = 100       # 最小买入数量（手）

    # ===== T+1卖出策略参数 =====
    context.sell_check_start_time = datetime.strptime("09:30:00", "%H:%M:%S").time()  # 卖出检查开始时间
    context.sell_check_end_time = datetime.strptime("10:00:00", "%H:%M:%S").time()    # 卖出检查结束时间
    context.strong_up_threshold = 1.08   # 强势上涨阈值 (8%)
    context.weak_up_threshold = 1.03     # 弱势上涨阈值 (3%)
    context.down_threshold = 0.97        # 下跌阈值 (3%)
    context.limit_up_hold_time = 600     # 涨停后持有时间(秒)
    # 移除强制卖出时间，如果涨停则持有到第二天

    # ===== 买入策略参数 =====
    context.volume_reduction_threshold = 0.4  # 挂单量减少阈值 (40%)

    # ===== 交易状态跟踪 =====
    context.last_order_volumes = {}      # 存储每只股票的上次挂单量
    context.pre_ticks = {}               # 存储上一个tick数据
    context.daily_signaled_stocks = set() # 每日已触发买入信号的股票
    context.position_records = {}        # 持仓记录，包含买入时间、成本等
    context.sell_check_records = {}      # 卖出检查记录

    # ===== 时间控制 =====
    context.monitor_interval = 3         # 监控间隔时间（秒）
    context.open_time = datetime.strptime("09:35:00", "%H:%M:%S").time()
    context.close_time = datetime.strptime("14:30:00", "%H:%M:%S").time()
    context.current_time = None
    context.current_date = datetime.now().date()

    # ===== 数据存储 =====
    context.daily_trades = []            # 每日交易记录
    context.success_count = 0            # 成功交易计数
    context.total_count = 0              # 总交易计数

    # 获取股票基本信息
    en_list = get_entity_list()
    map_info = {}
    for en in en_list:
        map_info[en["id"]] = en
    context.stock_base_info = map_info

    # ===== 从数据库获取数据 =====
    # 从数据库获取昨日涨停股票列表
    context.pre_limit_up_stocks = set()
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    db_manager = get_db_manager()
    zt_stocks = db_manager.get_zt_stocks_by_date(yesterday)
    context.pre_limit_up_stocks = set(zt_stocks)
    logger.info(f"成功从数据库加载昨日涨停股列表，共{len(context.pre_limit_up_stocks)}只")

    # 从数据库获取热门股票池
    context.hot_stocks = set()
    hot_stocks = db_manager.get_hot_stocks_from_pool('hot')
    context.hot_stocks = set(hot_stocks)
    logger.info(f"成功从数据库加载热门股票池，共{len(context.hot_stocks)}只")

    logger.info("涨停板策略高级版初始化完成")

def before_trading(context):
    """盘前初始化"""
    # 重置每日状态
    context.last_order_volumes.clear()
    context.daily_signaled_stocks.clear()
    context.daily_trades = []
    context.success_count = 0
    context.total_count = 0

    # 检查是否是新交易日
    today = datetime.now().date()
    if today != context.current_date:
        # 新交易日，清空卖出检查记录
        context.sell_check_records = {}
        context.current_date = today
        logger.info("新交易日开始，清空卖出检查记录")

    # 加载持仓记录（跨日持仓）
    load_position_records(context)

    logger.info("涨停板策略高级版盘前初始化完成")

def handle_tick(context, ticks):
    """处理tick数据"""
    current_time = datetime.fromtimestamp(list(ticks.values())[0].get('time', 0) / 1000)
    context.current_time = current_time
    current_time_of_day = current_time.time()

    # 根据交易日和时间执行不同逻辑
    if context.current_date == datetime.now().date():
        # 当天：处理买入逻辑
        if context.open_time <= current_time_of_day <= context.close_time:
            handle_buy_signals(context, ticks)
    else:
        # 次日：处理卖出逻辑（只在开盘后30分钟内）
        if context.sell_check_start_time <= current_time_of_day <= context.sell_check_end_time:
            handle_sell_signals(context, ticks)

def handle_buy_signals(context, ticks):
    """处理买入信号（当天）"""
    for stock_code, tick in ticks.items():
        # 基础过滤
        if not should_buy_stock(context, stock_code, tick):
            continue

        # 获取涨停价和5档行情
        upper_limit = context.stock_base_info[stock_code]['limit_up_price']
        ask_prices = tick.get('askPrice', [])
        ask_volumes = tick.get('askVol', [])

        # 检查涨停价是否存在
        if upper_limit not in ask_prices:
            continue

        # 获取涨停价对应的卖单量
        limit_up_index = ask_prices.index(upper_limit)
        current_volume = ask_volumes[limit_up_index] if limit_up_index < len(ask_volumes) else 0

        if current_volume == 0:
            continue

        # 获取上次挂单量
        last_volume = context.last_order_volumes.get(stock_code, current_volume)

        # 判断挂单量是否减少（触发买入条件）
        volume_reduction_ratio = (last_volume - current_volume) / max(last_volume, 1)
        if volume_reduction_ratio >= context.volume_reduction_threshold:
            # 执行买入
            buy_at_limit_up(context, stock_code, upper_limit, current_volume, volume_reduction_ratio)
            context.daily_signaled_stocks.add(stock_code)

        # 更新挂单量
        context.last_order_volumes[stock_code] = current_volume

def handle_sell_signals(context, ticks):
    """处理卖出信号（次日，只在开盘后30分钟内）"""
    current_time_of_day = context.current_time.time()

    # 只在开盘后30分钟内进行卖出检查，其他时间不进行任何卖出操作
    if not (context.sell_check_start_time <= current_time_of_day <= context.sell_check_end_time):
        return

    for stock_code, tick in ticks.items():
        if stock_code not in context.position_records:
            continue

        # 初始化卖出检查记录
        if stock_code not in context.sell_check_records:
            context.sell_check_records[stock_code] = {
                'check_start_time': context.current_time,
                'open_price': tick['lastPrice'],  # 开盘价
                'highest_price': tick['lastPrice'],
                'lowest_price': tick['lastPrice'],
                'current_price': tick['lastPrice'],
                'sell_decision': None
            }

        # 更新价格信息
        check_record = context.sell_check_records[stock_code]
        check_record['current_price'] = tick['lastPrice']
        check_record['highest_price'] = max(check_record['highest_price'], tick['lastPrice'])
        check_record['lowest_price'] = min(check_record['lowest_price'], tick['lastPrice'])

        # 检查是否可以做出卖出决定
        sell_decision = analyze_sell_decision(context, stock_code, check_record, tick)

        if sell_decision:
            check_record['sell_decision'] = sell_decision
            if sell_decision['action'] == 'SELL':
                sell_stock(context, stock_code, tick['lastPrice'], sell_decision['reason'])
            elif sell_decision['action'] == 'HOLD':
                logger.info(f"决定持有 {stock_code}: {sell_decision['reason']}")

def analyze_sell_decision(context, stock_code, check_record, tick):
    """分析卖出决定"""
    open_price = check_record['open_price']
    current_price = check_record['current_price']
    highest_price = check_record['highest_price']
    position_record = context.position_records[stock_code]
    buy_price = position_record['buy_price']

    upper_limit = context.stock_base_info[stock_code]['limit_up_price']

    # 计算涨幅
    change_ratio = (current_price - open_price) / open_price

    # 1. 如果开盘就涨停，坚决持有
    if current_price >= upper_limit:
        check_record['limit_up_time'] = context.current_time
        return {
            'action': 'HOLD',
            'reason': f'开盘涨停，坚决持有',
            'change_ratio': change_ratio
        }

    # 2. 如果开盘强势上涨（>8%），继续观察
    if change_ratio > context.strong_up_threshold:
        return {
            'action': 'HOLD',
            'reason': f'开盘强势上涨 {change_ratio:.1%}，继续观察',
            'change_ratio': change_ratio
        }

    # 3. 如果开盘温和上涨（3%-8%），根据买入成本判断
    if context.weak_up_threshold <= change_ratio <= context.strong_up_threshold:
        # 如果当前价格高于买入价，可以考虑持有
        if current_price > buy_price:
            return {
                'action': 'HOLD',
                'reason': f'温和上涨 {change_ratio:.1%}，价格高于成本，继续观察',
                'change_ratio': change_ratio
            }
        else:
            # 价格已回落到成本以下，卖出
            return {
                'action': 'SELL',
                'reason': f'温和上涨 {change_ratio:.1%}，但价格已回落到成本以下',
                'change_ratio': change_ratio
            }

    # 4. 如果开盘下跌或小幅上涨，卖出
    if change_ratio < context.weak_up_threshold:
        reason = f'开盘走势疲弱 {change_ratio:.1%}'
        if change_ratio < context.down_threshold:
            reason += '，出现下跌'
        return {
            'action': 'SELL',
            'reason': reason,
            'change_ratio': change_ratio
        }

    # 5. 检查是否已涨停后回落
    if 'limit_up_time' in check_record:
        limit_up_duration = (context.current_time - check_record['limit_up_time']).total_seconds()
        if limit_up_duration > context.limit_up_hold_time and current_price < upper_limit:
            return {
                'action': 'SELL',
                'reason': f'涨停后回落，持有{limit_up_duration:.0f}秒后卖出',
                'change_ratio': change_ratio
            }

    return None

def force_sell_all_positions(context):
    """强制卖出所有持仓"""
    for stock_code in list(context.position_records.keys()):
        if stock_code in context.position_records:
            tick = context.pre_ticks.get(stock_code, {})
            current_price = tick.get('lastPrice', 0)
            if current_price > 0:
                sell_stock(context, stock_code, current_price, "强制卖出")
            else:
                logger.warning(f"无法获取 {stock_code} 当前价格，跳过强制卖出")

def should_buy_stock(context, stock_code, tick):
    """判断是否应该买入股票"""
    # 基础过滤
    stock_name = context.stock_base_info[stock_code].get('name', '')
    if 'ST' in stock_name or 'st' in stock_name:
        return False

    # 过滤昨日涨停股票
    if stock_code in context.pre_limit_up_stocks:
        return False

    # 过滤已触发信号的股票
    if stock_code in context.daily_signaled_stocks:
        return False

    # 必须在热门股票池中
    if stock_code not in context.hot_stocks:
        return False

    # 风控检查
    if not check_buy_risk_control(context, stock_code):
        return False

    return True

def check_buy_risk_control(context, stock_code):
    """买入风控检查"""
    # 检查总持仓数量限制
    current_positions = len(context.position_records)
    if current_positions >= context.max_total_positions:
        return False

    # 检查是否已有该股票持仓
    if stock_code in context.position_records:
        return False

    return True

def buy_at_limit_up(context, stock_code, price, current_volume, volume_reduction_ratio):
    """以涨停价买入"""
    # 计算买入数量
    available_cash = context.max_single_position
    buy_volume = int(available_cash / price / 100 +1) * 100

    if buy_volume < context.min_order_volume:
        logger.warning(f"买入数量 {buy_volume} 少于最小要求 {context.min_order_volume}，跳过")
        return

    # 生成订单ID
    order_id = str(random.randint(1000000, 9999999))

    # 保存买入信号到数据库
    db_manager = get_db_manager()
    signal_saved = db_manager.save_strategy_signal(
        strategy_name='limit_up_strategy_advanced',
        stock_code=stock_code,
        signal_type='BUY',
        price=price,
        volume=buy_volume,
        order_id=order_id,
        status='PENDING'
    )

    if signal_saved:
        logger.info(f"策略信号已保存: {stock_code} - BUY - {price}")

    # 执行买入
    if context.account.buy_fix_price(stock_code, buy_volume, price):
        logger.info(f"买入成功: {stock_code}, 价格: {price}, 数量: {buy_volume}")

        # 更新信号状态
        db_manager.update_signal_status_by_order_id(order_id, 'EXECUTED')

        # 记录持仓信息
        context.position_records[stock_code] = {
            'buy_price': price,
            'buy_volume': buy_volume,
            'buy_time': context.current_time,
            'order_id': order_id,
            'volume_reduction_ratio': volume_reduction_ratio
        }

        # 记录交易
        trade_record = {
            'date': context.current_time.strftime("%Y-%m-%d %H:%M:%S"),
            'stock': stock_code,
            'action': 'BUY',
            'price': price,
            'volume': buy_volume,
            'order_id': order_id,
            'volume_reduction_ratio': volume_reduction_ratio
        }
        context.daily_trades.append(trade_record)
        context.total_count += 1

    else:
        logger.error(f"买入失败: {stock_code}")
        # 更新信号状态为取消
        db_manager.update_signal_status_by_order_id(order_id, 'CANCELLED')

def sell_stock(context, stock_code, current_price, sell_reason):
    """卖出股票"""
    if stock_code not in context.position_records:
        return

    position_record = context.position_records[stock_code]
    sell_volume = position_record['buy_volume']

    # 生成订单ID
    order_id = str(random.randint(1000000, 9999999))

    # 保存卖出信号到数据库
    db_manager = get_db_manager()
    signal_saved = db_manager.save_strategy_signal(
        strategy_name='limit_up_strategy_advanced',
        stock_code=stock_code,
        signal_type='SELL',
        price=current_price,
        volume=sell_volume,
        order_id=order_id,
        status='PENDING'
    )

    # 执行卖出
    if context.account.sell_fix_price(stock_code, current_price, sell_volume):
        logger.info(f"卖出成功: {stock_code}, 价格: {current_price}, 原因: {sell_reason}")

        # 更新信号状态
        db_manager.update_signal_status_by_order_id(order_id, 'EXECUTED')

        # 计算盈亏
        buy_price = position_record['buy_price']
        pnl = (current_price - buy_price) * sell_volume * 100  # 总盈亏

        # 记录交易
        trade_record = {
            'date': context.current_time.strftime("%Y-%m-%d %H:%M:%S"),
            'stock': stock_code,
            'action': 'SELL',
            'price': current_price,
            'volume': sell_volume,
            'order_id': order_id,
            'sell_reason': str(sell_reason),
            'pnl': pnl,
            'hold_days': 1  # T+1策略，持有1天
        }
        context.daily_trades.append(trade_record)

        # 移除持仓记录
        del context.position_records[stock_code]
        # 移除卖出检查记录
        if stock_code in context.sell_check_records:
            del context.sell_check_records[stock_code]

    else:
        logger.error(f"卖出失败: {stock_code}")
        db_manager.update_signal_status_by_order_id(order_id, 'CANCELLED')

def load_position_records(context):
    """加载持仓记录"""
    # 从数据库获取持仓记录（未卖出的持仓）
    db_manager = get_db_manager()

    # 查询未卖出的买入信号
    buy_signals = db_manager.get_strategy_signals(
        strategy_name='limit_up_strategy_advanced',
        signal_type='BUY',
        status='EXECUTED'
    )

    context.position_records = {}
    for signal in buy_signals:
        stock_code = signal['stock_code']
        # 检查是否有对应的卖出信号
        sell_signals = db_manager.get_strategy_signals(
            strategy_name='limit_up_strategy_advanced',
            stock_code=stock_code,
            signal_type='SELL',
            status='EXECUTED'
        )

        # 如果没有卖出信号，则认为还在持仓
        if not sell_signals:
            context.position_records[stock_code] = {
                'buy_price': signal['price'],
                'buy_volume': signal['volume'],
                'buy_time': signal['timestamp'],
                'order_id': signal['order_id']
            }

    logger.info(f"加载持仓记录完成，共{len(context.position_records)}只股票")

def save_position_records(context):
    """保存持仓记录（实际不需要保存，数据库已有记录）"""
    pass

def after_trading(context):
    """盘后处理"""
    # 保存持仓记录到数据库（实际上数据库已有记录，这里主要是清理）
    save_position_records(context)

    context.account.save_daily_account_info('limit_up_strategy_advanced')

    # 输出当日统计
    logger.info(f"当日统计 - 交易次数: {context.total_count}, 持仓数量: {len(context.position_records)}")
    logger.info(f"当日交易记录: {context.daily_trades}")
