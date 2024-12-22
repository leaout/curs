# coding: utf-8
from curs.engine import *
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

    @classmethod
    def __from_create__(cls, order_book_id, quantity, side,  frozen_price):
        # env = Environment.get_instance()
        order = cls()
        order._order_id = next(order.order_id_gen)
        # order._calendar_dt = env.calendar_dt
        # order._trading_dt = env.trading_dt
        order._quantity = quantity
        order._order_book_id = order_book_id
        order._side = side
        order._position_effect = None
        order._message = ""
        order._filled_quantity = 0
        order._status = ORDER_STATUS.PENDING_NEW

        order._frozen_price = frozen_price
        order._type = ORDER_TYPE.MARKET
        order._avg_price = 0
        order._transaction_cost = 0
        return order


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

    @classmethod
    def __from_create__(
            cls, order_id, price, amount, side, position_effect, order_book_id, commission=0., tax=0.,
            trade_id=None, close_today_amount=0, frozen_price=0, calendar_dt=None, trading_dt=None
    ):
        # env = Environment.get_instance()
        trade = cls()
        # trade._calendar_dt = calendar_dt or env.calendar_dt
        # trade._trading_dt = trading_dt or env.trading_dt
        trade._price = price
        trade._amount = amount
        trade._order_id = order_id
        trade._commission = commission
        trade._tax = tax
        trade._trade_id = trade_id if trade_id is not None else next(trade.trade_id_gen)
        trade._close_today_amount = close_today_amount
        trade._side = side
        trade._position_effect = position_effect
        trade._order_book_id = order_book_id
        trade._frozen_price = frozen_price
        return trade


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
            td.last_quantity = order.quantity
            td.last_price = deal_price

            if  order.price > deal_price:
                #成交
                order.fill(td)
            else:
                return
            #update account
            # if not account._positions.has_key(order_book_id):
            if   order_book_id not in  account._positions.keys():
                account._positions[order.order_book_id] = Position()

            account._positions[order.order_book_id].sid = order.order_book_id
            account._positions[order.order_book_id].avg_price = order._avg_price
            print(account._positions)
            #account._positions[order.order_book_id].quantity = 0
            # quantity = account._positions[order.order_book_id].quantity
            # print(quantity)
            account._positions[order.order_book_id].quantity += order.filled_quantity
            account._total_cash -= (order._avg_price * order.filled_quantity)

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
    od = Order.__from_create__('600000.XSHG',100,SIDE.BUY,13)
    # order_dict = {
    #     'order_id':123,
    #     'calendar_dt':None,
    #     'trading_dt': 20190602,
    #     'order_book_id':'600000.XSHG',
    #     'quantity': 100,
    #     'side': SIDE.BUY,
    #     'filled_quantity':0,
    #     'message': None,
    #     'secondary_order_id': None,
    #     'status': None,
    #     'frozen_price': 13,
    #     'type': None,
    #     'transaction_cost': None,
    #     'avg_price': 13,
    #     'position_effect': None,
    #
    # }
    # od.set_state(order_dict)
    orders = (acct,od)
    simu.add_order(orders)
    print(acct.positions['600000.XSHG'].__dict__ )
    print(acct.__dict__)
    # print(orders)
    # simu.
if __name__ == '__main__':
    main()