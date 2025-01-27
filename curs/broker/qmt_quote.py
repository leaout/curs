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
    # print(stocks)
    callback = partial(on_data, event_bus)
    sid = xtdata.subscribe_whole_quote(stocks, callback=callback)

    """阻塞线程接收行情回调"""
    import time

    client = xtdata.get_client()
    while True:
        time.sleep(3)
        if not client.is_connected():
            # raise Exception("行情服务连接断开")
            logger.warning("行情服务连接断开")
        # current_timestamp = now_pd_timestamp()
        # if current_timestamp.hour >= 15 and current_timestamp.minute >= 10:
        #     logger.info(f"record tick finished at: {current_timestamp}")
        #     break
    xtdata.unsubscribe_quote(sid)


if __name__ == "__main__":
    record_tick()

