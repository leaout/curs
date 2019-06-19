# coding: utf-8

class CursGlobal:
    def __init__(self,event_bus,config = None):
        self.__event_bus = event_bus
        self.__config= config
        self._stock_map = {}
        self._index_map = {}
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