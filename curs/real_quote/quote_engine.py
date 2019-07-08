# coding: utf-8
from .tdx_to_buddle import *
from curs.events import *

def get_security_type(order_book_id):
    '''
    获取证券类型
    :param order_book_id 600000.XSHG:
    :return:
    '''
    if order_book_id is None:
        return None
    list = order_book_id.split('.')
    if list[1] == "XSHG" and int(list[0]) < 600000:
        return SECURITY_TYPE.INDEX

    if list[1] == "XSHE" and int(list[0]) >= 399001:
        return SECURITY_TYPE.INDEX
    return SECURITY_TYPE.STOCK

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
                _(u"Environment has not been created. Please Use `QuoteEngine.get_instance()` after Curs init"))
        return QuoteEngine._quote_engine

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
        for k in self._min_substocks:
            type = get_security_type(k)
            min_arr = get_real_min(k, type)
            if type == SECURITY_TYPE.STOCK:
                self.__cursglobal.stock_map[k]["1m"] = min_arr
            if type == SECURITY_TYPE.INDEX:
                self.__cursglobal.index_map[k]["1m"] = min_arr


    def __process(self):
        while self.__is_runing:
            #get time
            self.__cursglobal.real_dt = datetime.datetime.now()
            # get full market quote
            self.get_full_quote()
            # get today min klines
            self.get_sub_min_klines()

            event = Event(EVENT.TICK, tick=1)
            self.__event_bus.put_event(event)
            time.sleep(3)

    def start(self):
        self.get_security_map()
        self.__is_runing = True
        handle_thread = Thread(target=self.__process, name="QuoteEngine")
        handle_thread.start()

    # @classmethod
    def add_min_subcriber(self,subcriber):
        self._min_substocks.append(subcriber)

