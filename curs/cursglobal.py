# coding: utf-8
from curs.events import *
from curs.data_source.data_buddle import *

class CursGlobal:
    def __init__(self,event_bus,config = None):
        CursGlobal._global = self
        self.__event_bus = event_bus
        self.__config= config
        self._stock_map = {}
        self._index_map = {}
        self._min_buddles = None
        self._day_buddles = None
        # real trade time
        self.real_dt = None

    @classmethod
    def get_instance(cls):
        """
        返回已经创建的 CursGlobal 对象
        """
        if CursGlobal._global is None:
            raise RuntimeError(
                _(u"Environment has not been created. Please Use `Environment.get_instance()` after RQAlpha init"))
        return CursGlobal._global

    @property
    def stock_map(self):
        return self._stock_map

    @stock_map.setter
    def stock_map(self, stock_map):
        if stock_map is None:
            raise ValueError('invalid security_map')
        self._stock_map = stock_map

    @property
    def index_map(self):
        return self._index_map

    @index_map.setter
    def index_map(self, index_map):
        if index_map is None:
            raise ValueError('invalid security_map')
        self._index_map = index_map

    def load_buddles(self):
        self._min_buddles = DataBuddle(self.__config["data_bundle_path"] + "\min", "r")
        self._min_buddles.open()
        self._day_buddles = DataBuddle(self.__config["data_bundle_path"] + "\day", "r")
        self._day_buddles.open()
        pass
