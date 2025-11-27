# -*- coding: utf-8 -*-
import logging
import time

import numpy as np
import pandas as pd
from xtquant import xtdata
from functools import partial
from curs.events import *
# https://dict.thinktrader.net/nativeApi/start_now.html?id=e2M5nZ

logger = logging.getLogger(__name__)

def _to_zvt_entity_id(qmt_code):
    code, exchange = qmt_code.split(".")
    exchange = exchange.lower()
    return f"stock_{exchange}_{code}"

def _qmt_instrument_detail_to_stock(stock_detail):
    exchange = stock_detail["ExchangeID"].lower()
    code = stock_detail["InstrumentID"]
    name = stock_detail["InstrumentName"]
    list_date = stock_detail["OpenDate"]
    end_date = stock_detail["ExpireDate"]
    pre_close = stock_detail["PreClose"]
    limit_up_price = stock_detail["UpStopPrice"]
    limit_down_price = stock_detail["DownStopPrice"]
    float_volume = stock_detail["FloatVolume"]
    total_volume = stock_detail["TotalVolume"]

    upper_exchange = exchange.upper()
    entity_id = f"{code}.{upper_exchange}"

    return {
        "id": entity_id,
        "entity_id": entity_id,
        "timestamp": list_date,
        "entity_type": "stock",
        "exchange": exchange,
        "code": code,
        "name": name,
        "list_date": list_date,
        "end_date": end_date,
        "pre_close": pre_close,
        "limit_up_price": limit_up_price,
        "limit_down_price": limit_down_price,
        "float_volume": float_volume,
        "total_volume": total_volume,
    }

def get_entity_list():
    stocks = get_qmt_stocks()
    entity_list = []

    for stock in stocks:
        stock_detail = xtdata.get_instrument_detail(stock, False)
        if stock_detail:
            entity_list.append(_qmt_instrument_detail_to_stock(stock_detail))
    return entity_list

def get_qmt_stocks():
    return xtdata.get_stock_list_in_sector("沪深A股")

def download_capital_data():
    stocks = get_qmt_stocks()
    xtdata.download_financial_data2(
        stock_list=stocks, table_list=["Capital"], start_time="", end_time="", callback=lambda x: print(x)
    )

def on_data(event_bus, datas):
    # print("reviced data")
    # print(datas.keys())
    event_bus.put_event(Event(EVENT.TICK, tick=datas)) 
    pass
    # for stock_code in datas:
    #     	print(stock_code, datas[stock_code])

def record_tick(event_bus):
    stocks = get_qmt_stocks()
    
    # 重连配置
    max_retries = 5  # 最大重试次数
    retry_count = 0  # 当前重试次数
    base_reconnect_delay = 5  # 基础重连延迟（秒）
    max_reconnect_delay = 60  # 最大重连延迟（秒）
    
    while retry_count < max_retries:
        try:
            logger.info(f"开始订阅行情数据，尝试次数: {retry_count + 1}")
            
            # 创建回调函数
            callback = partial(on_data, event_bus)
            
            # 订阅行情
            sid = xtdata.subscribe_whole_quote(stocks, callback=callback)
            logger.info(f"行情订阅成功，订阅ID: {sid}")
            
            # 重置重试计数
            retry_count = 0
            
            # 获取客户端连接
            client = xtdata.get_client()
            
            # 主循环，持续检查连接状态
            while True:
                time.sleep(3)
                
                if not client.is_connected():
                    logger.warning("行情服务连接断开，准备重连")
                    break
                    
                # 检查是否到达收盘时间（可选）
                # current_timestamp = now_pd_timestamp()
                # if current_timestamp.hour >= 15 and current_timestamp.minute >= 10:
                #     logger.info(f"record tick finished at: {current_timestamp}")
                #     return
                    
        except Exception as e:
            logger.error(f"行情订阅过程中发生异常: {e}")
        
        # 连接断开或异常后的重连逻辑
        retry_count += 1
        
        if retry_count >= max_retries:
            logger.error(f"已达到最大重试次数 {max_retries}，停止重连")
            break
            
        # 计算退避延迟时间（指数退避）
        delay = min(base_reconnect_delay * (2 ** (retry_count - 1)), max_reconnect_delay)
        logger.info(f"等待 {delay} 秒后尝试重连...")
        time.sleep(delay)
        
        # 清理资源（如果可能）
        try:
            if 'sid' in locals():
                xtdata.unsubscribe_quote(sid)
                logger.info("已清理之前的订阅")
        except Exception as e:
            logger.warning(f"清理订阅时发生异常: {e}")
    
    logger.error("行情服务最终连接失败，程序退出")

if __name__ == "__main__":
    record_tick()