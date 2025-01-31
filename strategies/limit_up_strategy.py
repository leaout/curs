# coding: utf-8
from curs.log_handler.logger import logger
from curs.cursglobal import *
from curs.api import *
from curs.broker.account import Account,Position
import json
import os
import random

# 初始化策略
def init(context):
    """初始化涨停板策略"""
    logger.info("初始化涨停板策略")
    # 初始化账户
    context.account = Account(total_cash=100000)  # 初始资金为10万元
    # 存储每只股票的上次挂单量
    context.last_order_volumes = {}
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
    context.data_file = os.path.join(context.data_dir, 'limit_up_trades.json')
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
    
    # 保存并重置每日记录
    if context.daily_trades:
        # 标记交易是否成功
        for trade in context.daily_trades:
            trade['success'] = trade.get('current_price', 0) >= trade['price']
        context.historical_trades.extend(context.daily_trades)
        save_historical_trades(context)
        
    context.daily_trades = []
    context.success_count = 0
    context.total_count = 0
    
    logger.info("涨停板策略初始化完成")

def handle_tick(context, ticks):
    """处理tick数据"""
    for stock_code, tick in ticks.items():
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
            
        # 获取5档行情
        ask_prices = tick.get('askPrice', [])
        ask_volumes = tick.get('askVol', [])
        
        # 获取涨停价
        upper_limit = context.stock_base_info[stock_code]['limit_up_price']
        
        # 检查5档行情中是否有涨停价
        if upper_limit in ask_prices:
            # 获取涨停价对应的卖单量
            limit_up_index = ask_prices.index(upper_limit)
            current_volume = ask_volumes[limit_up_index] if limit_up_index < len(ask_volumes) else 0
            
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
    # logger.info(f"涨停板买入：{stock_code}，价格：{price}")
    # 获取账户信息
    # account = context.account
    
    # 计算可买数量
    # available_cash = 10000
    # buy_volume = int(available_cash / price / 100) * 100  # 按手数买入
    
    # if buy_volume > 0:
    #     # 下单
    #     # order_id = account.buy(stock_code, price, buy_volume)
    #     order_id = random.randint(1000000, 9999999)  # 模拟订单号
    #     logger.info(f"涨停板买入：{stock_code}，价格：{price}，数量：{buy_volume}，订单号：{order_id}")
        
    #     # 记录交易
    #     trade_record = {
    #         'date': time.strftime("%Y-%m-%d %H:%M:%S"),
    #         'stock': stock_code,
    #         'price': price,
    #         'volume': buy_volume,
    #         'order_id': order_id
    #     }
    #     context.daily_trades.append(trade_record)
    #     context.total_count += 1

    # 获取账户信息
    account = context.account
    
    # 计算可买数量
    available_cash = 10000
    buy_volume = int(available_cash / price / 100) * 100  # 按手数买入
    
    if buy_volume > 0:
        # 下单
        if account.buy(stock_code, price, buy_volume):
            logger.info(f"涨停板买入：{stock_code}，价格：{price}，数量：{buy_volume}")
            
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
    logger.info(f"当日交易记录：{context.daily_trades}")
