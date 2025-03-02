from curs.log_handler.logger import logger
from curs.cursglobal import *
from curs.api import *
from curs.broker.account import Account, Position
import time
import json
import os
import random
import math

# 在这个方法中编写任何的初始化逻辑。context对象将会在你的算法策略的任何方法之间做传递。
def init(context):
    logger.info("init")
    # subscribe_min(context.s1)
    # QuoteEngine.add_min_subcriber("000001.XSHE")
    en_list = get_entity_list()
    map_info = {}
    for en in en_list:
        map_info[en["id"]] = en
    context.stock_base_info = map_info
    context.zt_list = []
    context.data_dir = os.path.join(os.getcwd(), 'data')

def before_trading(context):
    logger.info("策略初始化完成")


# 你选择的证券的数据更新将会触发此段逻辑，例如日或分钟历史数据切片或者是实时数据切片更新
def handle_bar(context, bar_dict):
    # 开始编写你的主要的算法逻辑

    # bar_dict[order_book_id] 可以拿到某个证券的bar信息
    # context.portfolio 可以拿到现在的投资组合状态信息

    # 使用order_shares(id_or_ins, amount)方法进行落单

    # TODO: 开始编写你的算法吧！
    if not context.fired:
        # order_percent并且传入1代表买入该股票并且使其占有投资组合的100%
        context.fired = True


def handle_tick(context,ticks):
    for stock_code, tick in ticks.items():
        # unix time to datetime,精确到毫秒
        current_time = datetime.fromtimestamp(tick.get('time', 0) / 1000)
        context.current_time= current_time
        # 过滤时间段:9:30-14:57
        if not (current_time.hour < 9 or (current_time.hour == 9 and current_time.minute < 15) or \
           current_time.hour > 14 or (current_time.hour == 14 and current_time.minute >= 59)):
             continue

        # 获取涨停价
        upper_limit = context.stock_base_info[stock_code]['limit_up_price']
        last_price = tick.get('lastPrice', 0) 
        if math.isclose(last_price ,upper_limit):
            # 记录涨停的股票到zt_list
            if stock_code not in context.zt_list:
                context.zt_list.append(stock_code)
                logger.info("涨停股票: %s, 价格: %s" % (stock_code, last_price))
    # after_trading(context)
            
        
        

def after_trading(context):
    logger.info("after_trading")
    #将zt_list写入文件，并记录日期
    date_str = context.current_time.strftime("%Y-%m-%d")
    file_name = "zt_list_%s.txt" % date_str
    file_name = context.data_dir+"/"+file_name
    with open(file_name, "w") as f:
        for stock_code in context.zt_list:
            f.write(stock_code + "\n")
    
    prefile_name = "zt_list_pre.txt"
    prefile_name = context.data_dir+"/"+prefile_name   
    with open(prefile_name, "w") as f:
        for stock_code in context.zt_list:
            f.write(stock_code + "\n")     
