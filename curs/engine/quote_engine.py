# coding: utf-8
# from .tdx_to_buddle import *
from curs.const import *
from curs.events import *
# from curs.real_quote import *
import numpy as np
import datetime
from curs.broker.qmt_quote import *

class QuoteEngine:
    def __init__(self,event_bus,cursglobal):
        QuoteEngine._quote_engine = self
        self.__event_bus = event_bus
        self.__is_runing = False
        self.__cursglobal = cursglobal
        #股票代码
        self.__stocks = []
        #指数代码
        self.__indexs = []
        # 订阅当日分钟线的股票
        self._min_substocks = []

    @classmethod
    def get_instance(cls):
        """
        返回已经创建的 CursGlobal 对象
        """
        if QuoteEngine._quote_engine is None:
            raise RuntimeError(
                (u"Environment has not been created. Please Use `QuoteEngine.get_instance()` after Curs init"))
        return QuoteEngine._quote_engine

    def get_full_quote(self):
        pass

    def init_security_map(self):
        pass


    def get_sub_min_klines(self):
        pass


    def __process(self):
        while self.__is_runing:
            record_tick(self.__event_bus)
            time.sleep(3)

    def start(self):
        self.init_security_map()
        self.__is_runing = True
        handle_thread = Thread(target=self.__process, name="QuoteEngine")
        handle_thread.start()

    # @classmethod
    def add_min_subcriber(self,subcriber):
        self._min_substocks.append(subcriber)

