# coding: utf-8

#  Copyright (c) 2019. Lorem ipsum dolor sit amet, consectetur adipiscing elit.
#  Morbi non lorem porttitor neque feugiat blandit. Ut vitae ipsum eget quam lacinia accumsan.
#  Etiam sed turpis ac ipsum condimentum fringilla. Maecenas magna.
#  Proin dapibus sapien vel ante. Aliquam erat volutpat. Pellentesque sagittis ligula eget metus.
#  Vestibulum commodo. Ut rhoncus gravida arcu.

import numpy as np
import talib as ta
#sar指标计算
def sarindicator(df):
    high = np.array(df.high, 'f8')
    low = np.array(df.low, 'f8')
    last= np.array(df.close, 'f8')
    lastpx = last[-1]

    sar = ta.SAR(high, low, acceleration=0.02, maximum=0.2)
    istrue = False

    if lastpx > sar[-1]:
        istrue = True

    return istrue


# 获取股票n日以来涨幅，根据当前价计算
# n 默认20日
def get_growth_rate(df):
    lc = df['close'][0]
    # c = data[security].close
    c = df['close'][-1]

    return (c - lc) / lc


# 计算平均价
def get_avg_price(df):
    # 取得过去N天的平均价格
    return df['close'].mean()
