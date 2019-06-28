# coding: utf-8
from .tdx_to_buddle import *
from curs.events import *

class QuoteEngine:
    def __init__(self,event_bus,cursglobal):
        self.__event_bus = event_bus
        self.__is_runing = False
        self.__cursglobal = cursglobal
        #股票代码
        self.__stocks = []
        #指数代码
        self.__indexs = []
        # 订阅当日分钟线的股票
        self.__min_subcribers = []

    def get_full_quote(self):
        stock_map = {}
        index_map = {}
        stock_quotes = get_security_quotes(self.__stocks)
        # print(self.__cursglobal.stock_map.keys())
        # print(stock_quotes.keys())
        for k in stock_quotes:
            # self.__cursglobal.stock_map.setdefault(k,{"quote", stock_quotes[k]})
            # stock_map[k].setdefault("quote",stock_quotes[k])
            if k not in self.__cursglobal.stock_map.keys():
                # print(k,"not in stock_map")
                continue
            self.__cursglobal.stock_map[k]["quote"]= stock_quotes[k]
            # stock_map[k] = {"quote": stock_quotes[k]}
        index_quotes = get_security_quotes(self.__indexs)
        for k in index_quotes:
            # index_map[k] = {"quote":index_quotes[k]}
            self.__cursglobal.index_map[k]["quote"] = index_quotes[k]
        # print(stock_map)
        # self.__cursglobal.stock_map = stock_map
        # self.__cursglobal.index_map = index_map

    def get_security_map(self):
        self.__stocks, self.__indexs = get_securities()
        #init stock map
        for k in self.__stocks:
            self.__cursglobal.stock_map[k] = {}
            # self.__cursglobal.stock_map.setdefault(k, {})
        for k in self.__indexs:
            # self.__cursglobal.index_map.setdefault(k, {})
            self.__cursglobal.index_map[k] = {}


    def get_sub_min_klines(self):
        for k in self.__min_subcribers:
            type = get_security_type(k)
            min_arr = day_quote_to_np(k,type)
            self.__cursglobal.index_map[k]["1m"] = min_arr


    def __process(self):
        while self.__is_runing:
            self.get_full_quote()
            self.get_sub_min_klines()
            event = Event(EVENT.TICK, tick=1)
            self.__event_bus.put_event(event)
            time.sleep(3)

    def start(self):
        self.get_security_map()
        self.__is_runing = True
        handle_thread = Thread(target=self.__process, name="QuoteEngine")
        handle_thread.start()

    def add_min_subcriber(self,subcriber):
        self.__min_subcribers.append(subcriber)

