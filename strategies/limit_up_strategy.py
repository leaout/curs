# coding: utf-8
from curs.log_handler.logger import logger
from curs.cursglobal import *
from curs.api import *
from curs.broker.qmt_account import QmtStockAccount,Position
from curs.database import get_db_manager
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
    qmt_path = CursGlobal.get_instance().config["base"]["accounts"]["qmt_path"]
    account_id = CursGlobal.get_instance().config["base"]["accounts"]["qmt_account_id"]
    trader_name = CursGlobal.get_instance().config["base"]["accounts"]["qmt_trader_name"]
    context.account = QmtStockAccount(path=qmt_path,account_id=account_id,trader_name=trader_name, total_cash=100000)  # 初始资金为10万元
    # 存储每只股票的上次挂单量
    context.last_order_volumes = {}
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
    #读取昨天zt_list 
    context.pre_limit_up_stocks = set()
    context.open_time = datetime.strptime("09:35:00", "%H:%M:%S").time()
    context.close_time = datetime.strptime("14:00:00", "%H:%M:%S").time()
    
    date_str = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    file_name = "/zt_list_pre.txt"
    file_name = context.data_dir+"/"+file_name
    with open(file_name,'r') as f:
        for line in f:
            context.pre_limit_up_stocks.add(line.strip())
    logger.info(f"成功加载昨日涨停股列表，共{len(context.pre_limit_up_stocks)}只")
    context.hot_stocks = set()
    load_stocks_fromfile(context, "/hotstocks.txt")
    
    
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
# 新增卖出处理函数
def sell_strategy(context,stock_code,tick):
    """次日卖出策略组合"""
    # 策略2：10:00-10:30卖出窗口        
    current_time = context.current_time.time()
    current_time_of_day = current_time.time()

    if not (datetime.time(10, 0) <= current_time_of_day <= datetime.time(10, 30)):
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
            log_sale('dynamic_stop', stock_code, order_volume)
    

    
    # 策略3：尾盘强制清仓
    if current_time >= datetime.time(14, 55):
        if context.account.sell_fix_price(stock_code, current_price, position.quantity):
            log_sale('force_close', stock_code, position.quantity)

def log_sale(strategy, code, vol):
    logger.info(f"[{strategy}] 卖出 {code} 数量 {vol} 时间 {datetime.now()}")

def handle_tick(context, ticks):
    """处理tick数据"""
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
    # return
    if context.pre_limit_up_stocks and stock_code in context.pre_limit_up_stocks:
        # logger.info(f"昨日涨停股票：{stock_code}，不再买入")
        return
    # 获取账户信息
    account = context.account

    # 计算可买数量
    available_cash = 30000
    buy_volume = int(available_cash / price / 100) * 100  # 按手数买入

    if buy_volume > 0:
        # 生成订单ID
        order_id = str(random.randint(1000000, 9999999))

        # 保存买入信号到数据库
        db_manager = get_db_manager()
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
            logger.error(f"保存策略信号到数据库失败: {stock_code}")

        # 下单
        if account.buy_fix_price(stock_code,buy_volume, price):
            logger.info(f"涨停板买入：{stock_code}，价格：{price}，数量：{buy_volume}, 时间：{context.current_time}")

            # 更新信号状态为已执行
            db_manager.update_signal_status_by_order_id(order_id, 'EXECUTED')

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
            logger.error(f"买入失败：{stock_code}，价格：{price}，数量：{buy_volume}")
            # 更新信号状态为取消
            db_manager.update_signal_status_by_order_id(order_id, 'CANCELLED')

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
