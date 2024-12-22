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





def get_qmt_stocks():
    return xtdata.get_stock_list_in_sector("沪深A股")




def download_capital_data():
    stocks = get_qmt_stocks()
    xtdata.download_financial_data2(
        stock_list=stocks, table_list=["Capital"], start_time="", end_time="", callback=lambda x: print(x)
    )




def on_data(event_bus, datas):
    print("reviced data")
    print(datas.keys())
    event_bus.put_event(Event(EVENT.TICK, tick=datas)) 
    pass
    # for stock_code in datas:
    #     	print(stock_code, datas[stock_code])
         
def record_tick(event_bus):
    # stocks = get_qmt_stocks()
    # print(stocks)
    callback = partial(on_data, event_bus)
    sid = xtdata.subscribe_whole_quote(['SH', 'SZ'], callback=callback)

    """阻塞线程接收行情回调"""
    import time

    client = xtdata.get_client()
    while True:
        time.sleep(3)
        if not client.is_connected():
            raise Exception("行情服务连接断开")
        # current_timestamp = now_pd_timestamp()
        # if current_timestamp.hour >= 15 and current_timestamp.minute >= 10:
        #     logger.info(f"record tick finished at: {current_timestamp}")
        #     break
    xtdata.unsubscribe_quote(sid)


if __name__ == "__main__":
    record_tick()

