# coding: utf-8
# from .tdx_to_buddle import *
from curs.const import *
from curs.events import *
# from curs.real_quote import *
import numpy as np
import datetime
import logging
from curs.broker.qmt_quote import *
from curs.broker.optimized_quote import OptimizedQuoteEngine
from curs.events_parallel import TickCache
from curs.core.schedule import EventsScheduler

logger = logging.getLogger(__name__)

class Engine:
    def __init__(self,event_bus,cursglobal, use_optimized: bool = True):
        Engine._quote_engine = self
        self.__event_bus = event_bus
        self.__is_runing = False
        self.__cursglobal = cursglobal
        self.__scheduler = EventsScheduler(event_bus)
        
        # 性能优化选项
        self.__use_optimized = use_optimized
        self.__quote_engine = None
        self.__tick_cache = TickCache(ttl_seconds=0.5)

    @classmethod
    def get_instance(cls):
        """
        返回已经创建的 CursGlobal 对象
        """
        if Engine._quote_engine is None:
            raise RuntimeError(
                (u"Environment has not been created. Please Use `QuoteEngine.get_instance()` after Curs init"))
        return Engine._quote_engine

    def get_full_quote(self):
        pass

    def init_security_map(self):
        pass


    def get_sub_min_klines(self):
        pass


    def __process(self):
        if self.__use_optimized:
            # 使用优化的行情引擎
            logger.info("使用优化版行情引擎")
            self.__quote_engine = OptimizedQuoteEngine(
                self.__event_bus, 
                stock_pool_name='hot'
            )
            self.__quote_engine.start()
            
            # 保持运行
            while self.__is_runing:
                time.sleep(3)
        else:
            # 使用原始行情引擎
            record_tick(self.__event_bus)
            while self.__is_runing:
                time.sleep(3)

    def start(self):
        self.init_security_map()
        self.__is_runing = True
        self.__scheduler.start()
        handle_thread = Thread(target=self.__process, name="QuoteEngine")
        handle_thread.start()
    
    def stop(self):
        """停止引擎"""
        self.__is_runing = False
        if self.__quote_engine:
            self.__quote_engine.stop()
        self.__scheduler.stop()

    # @classmethod
    def add_min_subcriber(self,subcriber):
        self._min_substocks.append(subcriber)
    
    def reload_stock_pool(self):
        """重新加载股票池"""
        if self.__quote_engine:
            self.__quote_engine.reload_stock_pool()
    
    def get_quote_stats(self):
        """获取行情统计"""
        if self.__quote_engine:
            return self.__quote_engine.get_stats()
        return {}

