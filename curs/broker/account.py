# coding: utf-8
import six

class Position(dict):
    '''
    持仓 id 成本均价 数量 当前价格
    '''
    def __init__(self):
        self._sid = 0
        self._avg_price = 0
        self._quantity = 0
        self._non_closable = 0  # 当天买入的不能卖出
        self._frozen = 0  # 冻结量
        self._transaction_cost = 0  # 交易费用
        self._last_price = 0  # 最新价

    def market_value(self):
        #返回市值
        return (self._quantity * self._last_price)

    @property
    def avg_price(self):
        return self._avg_price

    @avg_price.setter
    def avg_price(self,avg_price):
        if avg_price < 0 :
            raise ValueError('invalid avg_price')
        self._avg_price = avg_price

    @property
    def quantity(self):
        return self._quantity

    @quantity.setter
    def quantity(self, quantity):
        if quantity < 0:
            raise ValueError('invalid avg_price')
        self._quantity = quantity

    def update(self, quantity,avg_price):
        if quantity < 0 or avg_price <0:
            raise ValueError('invalid avg_price')

        self._avg_price = (self.avg_price * self.quantity + quantity * avg_price)/(self.quantity + quantity)
        self._quantity += quantity

    # def get_or_create(self, key):
    #     if key not in self:
    #         self[key] = self._position_cls(key)
    #     return self[key]


# class Positions(dict):
#     def __init__(self, position_cls):
#         super(Positions, self).__init__()
#         self._position_cls = position_cls
#         self._cached_positions = {}

class Account(object):

    def __init__(self, total_cash):
        self._positions = {}
        self._frozen_cash = 0
        self._total_cash = total_cash

    @property
    def market_value(self):
        """
        [float] 市值
        """
        return sum(position.market_value for position in six.itervalues(self._positions))

    @property
    def cash(self):
        """
        [float] 可用资金
        """
        return self._total_cash - self._frozen_cash

    @property
    def frozen_cash(self):
        """
        [float] 冻结资金
        """
        return self._frozen_cash

    @property
    def positions(self):
        """
        [dict] 持仓
        """
        return self._positions

    @property
    def transaction_cost(self):
        """
        [float] 总费用
        """
        return sum(position.transaction_cost for position in six.itervalues(self._positions))

    def update_account(self,order_book_id,quantity,avg_price):
        if order_book_id not in self.positions:
            self.positions[order_book_id]
        #update position
        self.positions[order_book_id].update(quantity,avg_price)

        pass