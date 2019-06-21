# coding: utf-8
from .tdx_to_buddle import *
from curs.events import *

class QuoteEngine:
    def __init__(self,event_bus,cursglobal):
        self.__event_bus = event_bus
        self.__is_runing = False
        self.__cursglobal = cursglobal
        self.__stocks = []
        self.__indexs = []

    def get_full_quote(self):
        stock_map = {}
        index_map = {}
        stock_quotes = get_security_quotes(self.__stocks)
        for k in stock_quotes:
            stock_map[k] = {"quote": stock_quotes[k]}
        index_quotes = get_security_quotes(self.__indexs)
        for k in index_quotes:
            index_map[k] = {"quote":index_quotes[k]}
        # print(stock_map)
        self.__cursglobal.stock_map = stock_map
        self.__cursglobal.index_map = index_map

    def get_security_map(self):
        self.__stocks, self.__indexs = get_securities()

    def __process(self):
        while self.__is_runing:
            self.get_full_quote()
            event = Event(EVENT.TICK, tick=1)
            self.__event_bus.put_event(event)
            time.sleep(3)

    def start(self):
        self.get_security_map()
        self.__is_runing = True
        handle_thread = Thread(target=self.__process, name="QuoteEngine")
        handle_thread.start()