# coding: utf-8
from curs.events import *
# from curs.data_source.data_buddle import *

class CursGlobal:
    def __init__(self,event_bus,config = None):
        CursGlobal._global = self
        self.__event_bus = event_bus
        self.__config= config
        self._stock_map = {}
        self._index_map = {}
        self.min_buddles = None
        self.day_buddles = None
        # real trade time
        self.real_dt = None
        self.data_source = None

    @classmethod
    def get_instance(cls):
        """
        返回已经创建的 CursGlobal 对象
        """
        if CursGlobal._global is None:
            raise RuntimeError(
                _(u"Environment has not been created. Please Use `CursGlobal.get_instance()` after  init"))
        return CursGlobal._global
    @property
    def config(self):
        return self.__config
    
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
        return None
        # self.min_buddles = DataBuddle(self.__config["base"]["data_bundle_path"] + "/min", "r")
        # self.min_buddles.open()
        # self.day_buddles = DataBuddle(self.__config["base"]["data_bundle_path"] + "/day", "r")
        # self.day_buddles.open()

    def set_data_source(self, data_source):
        self.data_source = data_source
