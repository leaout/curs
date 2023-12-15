from datetime import datetime
import backtrader as bt
from backtrader_plotting import Bokeh
from backtrader_plotting.schemes import Tradimo

# Create a subclass of Strategy to define the indicators and logic

class SmaCross(bt.Strategy):
    # list of parameters which are configurable for the strategy
    params = dict(
        pfast=20,  # period for the fast moving average
        pslow=110   # period for the slow moving average
    )

    def __init__(self):
        sma1 = bt.ind.SMA(period=self.p.pfast)  # fast moving average
        sma2 = bt.ind.SMA(period=self.p.pslow)  # slow moving average
        self.crossover = bt.ind.CrossOver(sma1, sma2)  # crossover signal

    def next(self):

        if not self.position:  # not in the market
            if self.crossover > 0:  # if fast crosses slow to the upside
                self.buy()  # enter long

        elif self.crossover < 0:  # in the market & cross to the downside
            self.close()  # close long position


cerebro = bt.Cerebro()  # create a "Cerebro" engine instance

# Create a data feed
# data = bt.feeds.YahooFinanceData(dataname='MSFT',
#                                  fromdate=datetime(2022, 1, 1),
#                                  todate=datetime(2022, 12, 31))
data = bt.feeds.GenericCSVData(dataname='../../analysis/600519.txt',  # CSV文件的路径
                               separator=",",
                               datetime=0,  # 日期字段在第0列
                               open=1,  # 开盘价字段在第1列
                               high=2,  # 最高价字段在第2列
                               low=3,  # 最低价字段在第3列
                               close=4,  # 收盘价字段在第4列
                               volume=6,  # 成交量字段在第6列
                               dtformat='%Y-%m-%d',  # 日期字段的格式
                               openinterest=-1,  # 没有持仓量字段
                               )


cerebro.adddata(data)  # Add the data feed


cerebro.addstrategy(SmaCross)  # Add the trading strategy
cerebro.run()  # run it all
b = Bokeh(style='bar', plot_mode='single', scheme=Tradimo())
cerebro.plot(b)
# cerebro.plot()  # and plot it with a single command