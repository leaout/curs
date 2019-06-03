# coding: utf-8
from curs.easydealutils import *
from curs.real_quote import *
from curs.const import *
from curs.broker.account import *
from curs.utils import *

class Order(object):

    order_id_gen = id_gen(int(time.time()) * 10000)

    def __init__(self):
        self._order_id = None
        self._secondary_order_id = None
        self._calendar_dt = None
        self._trading_dt = None
        self._quantity = None
        self._order_book_id = None
        self._side = None
        self._position_effect = None
        self._message = None
        self._filled_quantity = None
        self._status = None
        self._frozen_price = None
        self._type = None
        self._avg_price = None          #成交均价
        self._transaction_cost = None   #手续费

    def fill(self, trade):
        quantity = trade.last_quantity
        assert self.filled_quantity + quantity <= self.quantity
        new_quantity = self._filled_quantity + quantity
        self._avg_price = (self._avg_price * self._filled_quantity + trade.last_price * quantity) / new_quantity
        # self._transaction_cost += trade.commission + trade.tax
        self._filled_quantity = new_quantity
        if self.unfilled_quantity == 0:
            self._status = ORDER_STATUS.FILLED

    @property
    def quantity(self):
        """
        [int] 订单数量
        """
        if np.isnan(self._quantity):
            raise RuntimeError("Quantity of order {} is not supposed to be nan.".format(self.order_id))
        return self._quantity

    @property
    def unfilled_quantity(self):
        """
        [int] 订单未成交数量
        """
        return self.quantity - self.filled_quantity

    @property
    def order_id(self):
        """
        [int] 唯一标识订单的id
        """
        return self._order_id

    @property
    def price(self):
        """
        [float] 订单价格，只有在订单类型为'限价单'的时候才有意义
        """
        return  self._frozen_price

    @property
    def order_book_id(self):
        """
        [int] 唯一标识订单的id
        """
        return self._order_book_id

    @property
    def quantity(self):
        """
        [int] 订单数量
        """
        if np.isnan(self._quantity):
            raise RuntimeError("Quantity of order {} is not supposed to be nan.".format(self.order_id))
        return self._quantity

    @property
    def filled_quantity(self):
        """
        [int] 订单已成交数量
        """
        if np.isnan(self._filled_quantity):
            raise RuntimeError("Filled quantity of order {} is not supposed to be nan.".format(self.order_id))
        return self._filled_quantity

    def set_state(self, d):
        self._order_id = d['order_id']
        if 'secondary_order_id' in d:
            self._secondary_order_id = d['secondary_order_id']
        self._calendar_dt = d['calendar_dt']
        self._trading_dt = d['trading_dt']
        self._order_book_id = d['order_book_id']
        self._quantity = d['quantity']
        self._side = d['side']
        if d['position_effect'] is None:
            self._position_effect = None
        else:
            self._position_effect =  d['position_effect']
        self._message = d['message']
        self._filled_quantity = d['filled_quantity']
        self._status = d['status']
        self._frozen_price = d['frozen_price']
        self._type = d['type']
        self._transaction_cost = d['transaction_cost']
        self._avg_price = d['avg_price']

    def is_final(self):
        return self._status not in {
            ORDER_STATUS.PENDING_NEW,
            ORDER_STATUS.ACTIVE,
            ORDER_STATUS.PENDING_CANCEL
        }


class Trade(object):
    trade_id_gen = id_gen(int(time.time()) * 10000)

    def __init__(self):
        self._calendar_dt = None
        self._trading_dt = None
        self._price = None
        self._amount = None
        self._order_id = None
        self._commission = None
        self._tax = None
        self._trade_id = None
        self._close_today_amount = None
        self._side = None
        self._position_effect = None
        self._order_book_id = None
        self._frozen_price = None

    @property
    def last_quantity(self):
        if np.isnan(self._amount):
            raise RuntimeError("Last quantity of trade {} is not supposed to be nan.")
        return self._amount

    @last_quantity.setter
    def last_quantity(self,quantity):
        if np.isnan(self._amount):
            raise RuntimeError("Last quantity of trade {} is not supposed to be nan.")
        self._amount = quantity

    @property
    def last_price(self):
        if np.isnan(self._price):
            raise RuntimeError("Last price of trade {} is not supposed to be nan.")
        return self._price

    @last_price.setter
    def last_price(self,price):
        if np.isnan(self._price):
            raise RuntimeError("Last price of trade {} is not supposed to be nan.")
        self._price = price

class Matcher(object):

    def __init__(self):
        self._calendar_dt = None
        self._trading_dt = None

    def match(self, open_orders):
        # price_board = self._env.price_board
        for account, order in open_orders:
            order_book_id = order.order_book_id
            print(order_book_id)
            deal_price = self.get_last_price(order_book_id)
            # print(deal_price)
            td = Trade
            td.last_quantity = 100
            td.last_price = 13
            if  order.price > deal_price:
                #成交
                order.fill(td)

    def get_last_price(self,order_book_id):
        #获取最新价
        data = get_security_quotes([order_book_id])
        # print(data)
        for v in data[order_book_id]:
            if v == 'price':
                return  data[order_book_id][v]
        # return data[order_book_id]['price']

class Simulation(object):

    def __init__(self,matcher):
        self._matcher = matcher
        self._open_orders = []

    def _match(self,order_book_id=None):
        open_orders = self._open_orders
        if order_book_id is not None:
            open_orders = [(a, o) for (a, o) in self._open_orders if o.order_book_id == order_book_id]

        self._matcher.match(open_orders)
        final_orders = [(a, o) for a, o in self._open_orders if o.is_final()]
        self._open_orders = [(a, o) for a, o in self._open_orders if not o.is_final()]

        # for account, order in final_orders:
        #     if order.status == ORDER_STATUS.REJECTED or order.status == ORDER_STATUS.CANCELLED:
        #         self._env.event_bus.publish_event(Event(EVENT.ORDER_UNSOLICITED_UPDATE, account=account, order=order))
        #

    def add_order(self,orders):
        self._open_orders.append(orders)
        self._match()


def main():
    # bt = BuddleTools("H:/indexmincsv","H:/buddles")
    # bt.csv_to_carray()
    mer = Matcher()
    simu = Simulation(mer)
    acct = Account(100000)
    od = Order()
    order_dict = {
        'order_id':123,
        'calendar_dt':None,
        'trading_dt': 20190602,
        'order_book_id':'600000.XSHG',
        'quantity': 100,
        'side': SIDE.BUY,
        'filled_quantity':0,
        'message': None,
        'secondary_order_id': None,
        'status': None,
        'frozen_price': 13,
        'type': None,
        'transaction_cost': None,
        'avg_price': 13,
        'position_effect': None,

    }
    od.set_state(order_dict)
    orders = (acct,od)
    simu.add_order(orders)
    # print(orders)
    # simu.
if __name__ == '__main__':
    main()