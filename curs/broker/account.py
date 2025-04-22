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
        if quantity > 0:    
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
        return sum(position.market_value() for position in six.itervalues(self._positions))

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
            self.positions[order_book_id] = Position()
        #update position
        try:
            self.positions[order_book_id].update(quantity,avg_price)
        except:
            print("update_account error")
            pass

    def buy(self, stock_code, price, volume):
        """买入股票"""
        if self.cash >= price * volume:
            # 更新持仓
            self.update_account(stock_code, volume, price)

            return True
        else:
            return False
    
    def sell(self, stock_code, price, volume):
        """卖出股票"""
        if stock_code in self._positions and self._positions[stock_code].quantity >= volume:
            # 更新持仓
            self.update_account(stock_code, -volume, price)
            # 更新资金
            self._total_cash += price * volume
            return True
        else:
            return False
    def get_position(self, stock_code):
        """获取持仓"""
        if stock_code in self._positions:
            return self._positions[stock_code]
        else:
            return None
        
    def save_daily_account_info(self,strategy_name):
        """每日盘后存储账户信息"""
        import json
        from datetime import datetime
        import os

        # 创建账户信息字典
        account_info = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'total_cash': self._total_cash,
            'frozen_cash': self._frozen_cash,
            'market_value': self.market_value,
            'positions': {
                code: {
                    'quantity': pos.quantity,
                    'avg_price': pos.avg_price,
                    'market_value': pos.market_value()
                }
                for code, pos in self._positions.items()
            }
        }

        # 确保目录存在
        os.makedirs('data/account_records', exist_ok=True)

        # 保存到JSON文件
        filename = f"data/account_records/{strategy_name}_{datetime.now().strftime('%Y%m%d')}_account.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(account_info, f, ensure_ascii=False, indent=2)
