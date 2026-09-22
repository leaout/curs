# coding: utf-8
import logging
import time
from threading import Thread

from curs.core.schedule import EventsScheduler

logger = logging.getLogger(__name__)

class Engine:
    """Legacy scheduler shell retained without a bundled market provider."""

    def __init__(self, event_bus, cursglobal, use_optimized: bool = False):
        Engine._quote_engine = self
        self.__event_bus = event_bus
        self.__is_runing = False
        self.__cursglobal = cursglobal
        self.__scheduler = EventsScheduler(event_bus)
        
        self.__quote_engine = None

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
        logger.info("旧 Engine 未配置行情源，仅运行事件调度器")
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
        raise RuntimeError("旧 Engine 不再提供行情订阅，请使用 trading_v2.market")
    
    def reload_stock_pool(self):
        """重新加载股票池"""
        if self.__quote_engine:
            self.__quote_engine.reload_stock_pool()
    
    def get_quote_stats(self):
        """获取行情统计"""
        if self.__quote_engine:
            return self.__quote_engine.get_stats()
        return {}

