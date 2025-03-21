# coding: utf-8
from curs.log_handler.logger import logger
from curs.cursglobal import *
from curs.api import *
from curs.broker.account import Account, Position
import time
import json
import os
import random
from datetime import datetime, timedelta
import math

# 初始化策略
def init(context):
    """初始化涨停板策略"""
    logger.info("初始化涨停板策略")
    # 初始化账户
    context.account = Account(total_cash=100000)  # 初始资金为10万元
    # 存储每只股票的上次挂单量
    context.last_order_volumes = {}
    #pre ticks
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
    #读取昨天zt_list 
    context.pre_limit_up_stocks = set()
    context.open_time = datetime.strptime("09:30:00", "%H:%M:%S").time()
    context.close_time = datetime.strptime("14:57:00", "%H:%M:%S").time()
    
    date_str = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    file_name = "/zt_list_pre.txt"
    file_name = context.data_dir+"/"+file_name
    with open(file_name,'r') as f:
        for line in f:
            context.pre_limit_up_stocks.add(line.strip())
    context.hot_stocks = set()
    load_stocks_fromfile(context, "/hotstocks.txt")
    
    
def load_stocks_fromfile(context, file_name):
    """加载昨日的涨停股列表"""
    #清空昨日涨停股列表
    context.hot_stocks.clear()
    file_path = context.data_dir + file_name
    try:
        with open(file_path, 'r') as f:
            for line in f:
                context.hot_stocks.add(line.strip())
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
    # 清空挂单量记录
    context.last_order_volumes.clear()
    # 清空每日信号记录
    context.daily_signaled_stocks.clear()
    
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

def handle_tick(context, ticks):
    """处理tick数据"""
    for stock_code, tick in ticks.items():
#         'time' =
# 1739170800000
        # unix time to datetime,精确到毫秒
        current_time = datetime.fromtimestamp(tick.get('time', 0) / 1000)
        context.current_time= current_time
        current_time_of_day = current_time.time()
        # 过滤时间段:9:30-14:57
        if not (context.open_time <= current_time_of_day <= context.close_time):
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
                                                    
            # 判断挂单量是否减少1/4
            if current_volume <= last_volume * 0.75:
                # 触发买入
                buy_at_limit_up(context, stock_code, upper_limit)
                # 标记该股票已触发信号
                context.daily_signaled_stocks.add(stock_code)

                
            # 更新挂单量 取最大值
            context.last_order_volumes[stock_code] = current_volume


def buy_at_limit_up(context, stock_code, price):
    """以涨停价买入"""
    if context.pre_limit_up_stocks and stock_code in context.pre_limit_up_stocks:
        logger.info(f"昨日涨停股票：{stock_code}，不再买入")
        return
    # 获取账户信息
    account = context.account
    
    # 计算可买数量
    available_cash = account.cash
    buy_volume = int(available_cash / price / 100) * 100  # 按手数买入
    
    if buy_volume > 0:
        # 下单
        if account.buy(stock_code, price, buy_volume):
            logger.info(f"涨停板买入：{stock_code}，价格：{price}，数量：{buy_volume}, 时间：{context.current_time}")
            
            # 记录交易
            trade_record = {
                'date': time.strftime("%Y-%m-%d %H:%M:%S"),
                'stock': stock_code,
                'price': price,
                'volume': buy_volume,
                'order_id': random.randint(1000000, 9999999)  # 模拟订单号
            }
            context.daily_trades.append(trade_record)
            context.total_count += 1
        else:
            logger.error(f"买入失败：{stock_code}，价格：{price}，数量：{buy_volume}")

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
    # 检查当日交易结果
    check_trade_outcomes(context)
    save_historical_trades(context)
    context.account.save_daily_account_info('limit_up_strategy')
    logger.info(f"当日交易记录：{context.daily_trades}")
