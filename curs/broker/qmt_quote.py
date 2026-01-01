# -*- coding: utf-8 -*-
import logging
import time
from datetime import datetime

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

def get_stock_kline_data(stock_code, count=60):
    """获取股票K线数据"""
    try:
        # 首先下载历史数据（如果需要）
        try:
            # 下载最近60天的日K线数据
            xtdata.download_history_data(stock_code, period='1d', start_time='', end_time='')
        except Exception as download_error:
            print(f"下载历史数据失败: {download_error}")
            # 如果下载失败，继续尝试获取现有数据

        # 使用QMT获取日K线数据
        kline_data = xtdata.get_market_data(
            field_list=['time', 'open', 'high', 'low', 'close', 'volume', 'amount'],
            stock_list=[stock_code],
            period='1d',  # 日K线
            count=count  # 最近N天
        )

        if not kline_data or 'time' not in kline_data:
            return None

        # 获取各个字段的DataFrame
        time_df = kline_data['time']
        open_df = kline_data['open']
        high_df = kline_data['high']
        low_df = kline_data['low']
        close_df = kline_data['close']
        volume_df = kline_data['volume']

        # 检查是否有数据
        if stock_code not in time_df.index:
            return None

        # 提取该股票的数据
        times = time_df.loc[stock_code]
        opens = open_df.loc[stock_code]
        highs = high_df.loc[stock_code]
        lows = low_df.loc[stock_code]
        closes = close_df.loc[stock_code]
        volumes = volume_df.loc[stock_code]

        # 格式化数据为ECharts K线图格式 [开盘, 收盘, 最低, 最高]
        echarts_kline = []
        dates = []
        volume_list = []

        # 按时间顺序整理数据
        for i in range(len(times)):
            if pd.notna(times.iloc[i]) and pd.notna(opens.iloc[i]):
                try:
                    # QMT时间戳可能是毫秒格式，尝试转换
                    timestamp = times.iloc[i]
                    if timestamp > 1e10:  # 如果是毫秒时间戳
                        timestamp = timestamp / 1000

                    # 时间戳转换为日期字符串
                    date = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
                    dates.append(date)
                    echarts_kline.append([
                        float(opens.iloc[i]),  # open
                        float(closes.iloc[i]), # close
                        float(lows.iloc[i]),   # low
                        float(highs.iloc[i])   # high
                    ])
                    volume_list.append(float(volumes.iloc[i]))
                except (ValueError, OSError) as e:
                    # 如果时间戳转换失败，跳过这条数据
                    print(f"跳过无效时间戳: {times.iloc[i]}, 错误: {e}")
                    continue

        if not dates:
            return None

        return {
            'stock_code': stock_code,
            'dates': dates,
            'kline_data': echarts_kline,
            'volumes': volume_list
        }
    except Exception as e:
        print(f"获取K线数据失败: {e}")
        return None

def get_stock_quote_data(stock_code):
    """获取股票当日行情数据"""
    try:
        # 使用get_market_data_ex获取最新分笔数据
        quote_data = xtdata.get_market_data_ex(
            field_list=['time', 'open', 'high', 'low', 'close', 'volume', 'amount'],
            stock_list=[stock_code],
            period='tick',  # 分笔数据
            count=1  # 最新一条
        )

        if quote_data and 'close' in quote_data and stock_code in quote_data['close'].index:
            close_df = quote_data['close']
            volume_df = quote_data['volume']
            amount_df = quote_data['amount']
            high_df = quote_data['high']
            low_df = quote_data['low']
            open_df = quote_data['open']

            last_price = float(close_df.loc[stock_code].iloc[-1]) if not close_df.loc[stock_code].empty else 0
            volume = int(volume_df.loc[stock_code].iloc[-1]) if not volume_df.loc[stock_code].empty else 0
            amount = float(amount_df.loc[stock_code].iloc[-1]) if not amount_df.loc[stock_code].empty else 0
            high = float(high_df.loc[stock_code].iloc[-1]) if not high_df.loc[stock_code].empty else 0
            low = float(low_df.loc[stock_code].iloc[-1]) if not low_df.loc[stock_code].empty else 0
            open_price = float(open_df.loc[stock_code].iloc[-1]) if not open_df.loc[stock_code].empty else 0

            # 获取股票基本信息
            instrument_detail = xtdata.get_instrument_detail(stock_code, False)
            stock_name = instrument_detail.get('InstrumentName', '') if instrument_detail else ''

            # 获取昨收价用于计算涨跌幅
            try:
                # 获取前一天的数据来获取昨收价
                pre_data = xtdata.get_market_data(
                    field_list=['close'],
                    stock_list=[stock_code],
                    period='1d',
                    count=2  # 获取最近2天的数据
                )
                if pre_data and 'close' in pre_data and stock_code in pre_data['close'].index:
                    close_df_pre = pre_data['close']
                    pre_close = float(close_df_pre.loc[stock_code].iloc[-2]) if len(close_df_pre.loc[stock_code]) >= 2 else last_price
                else:
                    pre_close = last_price
            except:
                pre_close = last_price

            # 计算涨跌幅和涨跌额
            change = last_price - pre_close
            change_percent = (change / pre_close * 100) if pre_close > 0 else 0

            return {
                'stock_code': stock_code,
                'name': stock_name,
                'price': float(last_price),
                'change': float(change),
                'change_percent': float(change_percent),
                'volume': int(volume),
                'amount': float(amount),
                'high': float(high),
                'low': float(low),
                'open': float(open_price),
                'close': float(pre_close),
                'turnover': 0.0,  # QMT不直接提供换手率
                'pe': None,  # QMT不直接提供市盈率
                'market_cap': None,  # QMT不直接提供市值
                'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        else:
            return None
    except Exception as e:
        print(f"获取行情数据失败: {e}")
        return None

if __name__ == "__main__":
    record_tick()
