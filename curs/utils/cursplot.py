#  Copyright (c) 2019. Lorem ipsum dolor sit amet, consectetur adipiscing elit.
#  Morbi non lorem porttitor neque feugiat blandit. Ut vitae ipsum eget quam lacinia accumsan.
#  Etiam sed turpis ac ipsum condimentum fringilla. Maecenas magna.
#  Proin dapibus sapien vel ante. Aliquam erat volutpat. Pellentesque sagittis ligula eget metus.
#  Vestibulum commodo. Ut rhoncus gravida arcu.

# -*- coding:utf-8 -*-

import matplotlib.pyplot as plt
#pip install https://github.com/matplotlib/mpl_finance/archive/master.zip
from mpl_finance import candlestick_ochl
import datetime
from matplotlib.pylab import date2num
from curs.api import *
import matplotlib.ticker as ticker
from .indicator import *

def candles_plot(df,order_book_id):
    df = df.dropna()
    # df = df.drop(columns=['money'])
    df = df.reset_index()
    df["indexxx"] = df.index
    # 生成横轴的刻度名字
    df['5'] = df.close.rolling(5).mean()
    df['20'] = df.close.rolling(20).mean()
    df['30'] = df.close.rolling(30).mean()
    df['60'] = df.close.rolling(60).mean()

    date_tickers = df.time
    #图层
    fig, (ax1, ax2, ax3) = plt.subplots(3, sharex=True,figsize=(1200 / 72, 480 / 72))

    def format_date(x, pos=None):
        # if x < 0 or x > len(date_tickers) - 1:
        #     return ''
        if x%5 != 0 or x > len(date_tickers) - 1:
            return ''
        return date_tickers[int(x)]
    #k线图
    ax1.xaxis.set_major_locator(ticker.MultipleLocator(6))
    #显示主要刻度
    ax1.xaxis.set_major_formatter(ticker.FuncFormatter(format_date))
    ax1.set_ylabel('Price')
    ax1.grid(True)
    ax1.set_title(order_book_id)
    # candlestick_ochl(ax1, quotes, colordown='#53c156', colorup='#ff1717', width=0.2)
    candlestick_ochl(ax1, df[['indexxx', 'open', 'close', 'high', 'low']].values,
                     colordown='#53c156', colorup='#ff1717', width=0.2)
    for ma in ['5', '20', '30', '60']:
        ax1.plot(df['indexxx'], df[ma])
    ax1.legend()

    #成交量
    # ax2.xaxis.set_major_formatter(ticker.FuncFormatter(format_date))
    df['up'] = df.apply(lambda row: 1 if row['close'] >= row['open'] else 0, axis=1)
    ax2.bar(df.query('up == 1')['indexxx'], df.query('up == 1')['volume'], color='r', alpha=0.7,width = 0.8)
    ax2.bar(df.query('up == 0')['indexxx'], df.query('up == 0')['volume'], color='g', alpha=0.7,width = 0.8)
    # plt.bar(df.volume,height = 1, width=0.5)
    ax2.set_ylabel('Volume')
    ax2.grid(True)

    #Macd
    wDif, wDea, wMacd = macd_cn(df.close, 12, 26, 9)
    wMacd = wMacd.fillna(0)
    wDea = wDea.fillna(0)
    wDif = wDif.fillna(0)
    # print(wDif)
    # print(df['indexxx'])
    df['macdup'] = wMacd.apply(lambda row: 1 if row > 0 else 0)
    df['macd'] = wMacd
    ax3.plot(df['indexxx'], wDif)
    ax3.plot(df['indexxx'], wDea)
    # ax3.bar(df['indexxx'], wMacd,width = 0.2)
    ax3.bar(df.query('macdup == 1')['indexxx'], df.query('macdup == 1')['macd'], color='r',width=0.2)
    ax3.bar(df.query('macdup == 0')['indexxx'], df.query('macdup == 0')['macd'], color='g',width=0.2)
    ax3.set_ylabel('Macd')
    ax3.grid(True)
    ax3.legend()

    plt.show()



if __name__ == "__main__":

    pass
