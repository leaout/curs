# coding: utf-8

#  Copyright (c) 2019. Lorem ipsum dolor sit amet, consectetur adipiscing elit.
#  Morbi non lorem porttitor neque feugiat blandit. Ut vitae ipsum eget quam lacinia accumsan.
#  Etiam sed turpis ac ipsum condimentum fringilla. Maecenas magna.
#  Proin dapibus sapien vel ante. Aliquam erat volutpat. Pellentesque sagittis ligula eget metus.
#  Vestibulum commodo. Ut rhoncus gravida arcu.

import numpy as np
import talib as ta
import types
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


#计算macd
'''
close = hData['close']
close = np.array(close, dtype='f8')
wDif, wDea, wMacd =  macd_cn(close, 12, 26, 9)
'''
def macd_cn(close_arr, fastperiod, slowperiod, signalperiod) :
    macdDIFF, macdDEA, macd = ta.MACDEXT(close_arr, fastperiod=fastperiod, fastmatype=1, slowperiod=slowperiod, slowmatype=1, signalperiod=signalperiod, signalmatype=1)
    macd = macd * 2
    return macdDIFF, macdDEA, macd


def trend_indicator(df):

    openpx = np.nan_to_num(np.array(df.open, 'f8'))
    high = np.nan_to_num(np.array(df.high, 'f8'))
    low = np.nan_to_num(np.array(df.low, 'f8'))
    close = np.nan_to_num(np.array(df.close, 'f8'))
    if len(close) < 10:
        return False

    # a =max((high[-1] - low[-1]),abs(high[-1] - closme[-2]),abs(low[-1] - close[-2]))

    # print a
    close = np.delete(close, -1)
    close = np.insert(close, 0, 0)

    ar1 = np.maximum((high - low), np.abs(high - close), np.abs(low - close))
    tr = np.sum(ar1[-7:])
    tr1 = np.sum(ar1[-9:-1])

    high1 = np.delete(high, -1)
    high1 = np.insert(high1, 0, 0)

    low1 = np.delete(low, -1)
    low1 = np.insert(low1, 0, 0)

    hd = high - high1
    ld = low1 - low

    ar1 = hd if hd[-1] > 0 and hd[-1] > ld[-1] else 0
    ar2 = ld if ld[-1] > 0 and ld[-1] > hd[-1] else 0
    if type(ar1) == types.IntType:
        dmp = 0
        dmp1 = 0
    else:
        dmp = np.sum(ar1[-7:])
        dmp1 = np.sum(ar1[-8:-1])

    if type(ar2) == types.IntType:
        dmm = 0
        dmm1 = 0
    else:
        dmm = np.sum(ar2[-7:])
        dmm1 = np.sum(ar2[-8:-1])

    pdi = dmp * 100 / tr
    mdi = dmm * 100 / tr

    pdi1 = dmp1 * 100 / tr1
    mdi1 = dmm1 * 100 / tr1
    # buy
    if pdi1 < mdi1 and pdi > mdi:
        return 1
    # sell
    if mdi1 < pdi1 and mdi > pdi:
        return -1
    # none
    return 0


def is_3_black_crows(df):
    # talib.CDL3BLACKCROWS

    # 三只乌鸦说明来自百度百科
    # 1. 连续出现三根阴线，每天的收盘价均低于上一日的收盘
    # 2. 三根阴线前一天的市场趋势应该为上涨
    # 3. 三根阴线必须为长的黑色实体，且长度应该大致相等
    # 4. 收盘价接近每日的最低价位
    # 5. 每日的开盘价都在上根K线的实体部分之内；
    # 6. 第一根阴线的实体部分，最好低于上日的最高价位
    #
    # 算法
    # 有效三只乌鸦描述众说纷纭，这里放宽条件，只考虑1和2
    # 根据前4日数据判断
    # 3根阴线跌幅超过4.5%（此条件忽略）

    h_close = list(df['close'])
    h_open = list(df['open'])

    if len(h_close) < 4 or len(h_open) < 4:
        return False

    # 一阳三阴
    if h_close[-4] > h_open[-4] \
            and (h_close[-1] < h_open[-1] and h_close[-2] < h_open[-2] and h_close[-3] < h_open[-3]):
        # and (h_close[-1] < h_close[-2] and h_close[-2] < h_close[-3]) \
        # and h_close[-1] / h_close[-4] - 1 < -0.045:
        return True
    return False