# coding=utf-8

from curs.real_quote import *
from curs.data_source import *
from curs.utils import *
from curs.const import *

def min_quote_to_np(code, type):
    '''
    获取当日分钟线
    type index stock
    :param code:"600004.XSHG"
    :return: 返回 np.array
    '''
    if type == SECURITY_TYPE.STOCK:
        df = get_security_kline(code, 240)
    elif type == SECURITY_TYPE.INDEX:
        df = get_index_kline(code, 240)
    if df.empty :
        return None
    df = reset_col(df)

    df['datetime'] = df['datetime'].map(timestamp_to_unix_ext)
    bt = BuddleTools()
    return bt.df_to_np(df)

def get_real_min(code, type):
    '''
    获取当日分钟线
    type index stock
    :param code:"600004.XSHG"
    :return: 返回 np.array
    '''
    k_counts = get_today_kline_counts()
    if k_counts is None:
        return None
    if type == SECURITY_TYPE.STOCK:
        df = get_security_kline(code, k_counts)
    elif type == SECURITY_TYPE.INDEX:
        df = get_index_kline(code, k_counts)
    if df.empty or df is None :
        return None

    df = reset_col(df)

    if df is None:
        return None

    df['datetime'] = df['datetime'].map(timestamp_to_unix_ext)
    bt = BuddleTools()
    return bt.df_to_np(df)

def day_quote_to_np(code, type):
    '''
    获取当日分钟线
    type index stock
    :param code:"600004.XSHG"
    :return: 返回 np.array
    '''
    if type == SECURITY_TYPE.STOCK:
        df = get_security_kline(code, 1,"1d")
    elif type == SECURITY_TYPE.INDEX:
        df = get_index_kline(code, 1,"1d")
    if df.empty :
        return None
    df = reset_col(df)

    df['datetime'] = df['datetime'].map(timestamp_to_unix_ext)
    bt = BuddleTools()
    return bt.df_to_np(df)

def get_index_quote_2np(code):
    '''
    获取当日分钟线
    :param code:"600004.XSHG"
    :return: 返回 np.array
    '''
    df = get_index_kline(code, 480)
    if df.empty :
        return None
    df = reset_col(df)

    df['datetime'] = df['datetime'].map(timestamp_to_unix_ext)
    bt = BuddleTools()
    return bt.df_to_np(df)

def get_securities():
    #stock
    stockdf = get_security_list()
    stocklist = df_to_securitylist(stockdf)
    #index
    indexdf = get_security_list("index")
    indexlist = df_to_securitylist(indexdf)

    return (stocklist,indexlist)


def df_to_securitylist(stockdf):
    flist = []
    if stockdf is None:
        return  flist
    stocklist = stockdf.index.tolist()

    for k in stocklist:
        market = "XSHG" if (k[1] == "sh") else "XSHE"
        bookid = k[0] + '.' + market
        flist.append(bookid)

    return flist

@function_eleapsed
def min_quote_to_buddle(root_dir):
    dtdb = DataBuddle(root_dir,'a')
    dtdb.open()
    slist,inlist = get_securities()
    for k in slist:
        # file_name = GetFileName(k)
        # if int(file_name) > 417:
        #     continue
        arr = min_quote_to_np(k, SECURITY_TYPE.STOCK)
        if arr is None:
            continue
        logger.info("security min quote:"+ k)
        dtdb.append(k,arr)

    #index
    for k in inlist:
        file_name = GetFileName(k)
        if int(file_name) >= 880001:
            continue
        # if int(file_name) <= 31:
        #     continue
        arr = min_quote_to_np(k, SECURITY_TYPE.INDEX)
        if arr is None:
            continue
        logger.info("security min quote:"+ k)
        dtdb.append(k,arr)
@function_eleapsed
def day_quote_to_buddle(root_dir):
    dtdb = DataBuddle(root_dir,'a')
    dtdb.open()
    slist,inlist = get_securities()
    for k in slist:
        # file_name = GetFileName(k)
        # if int(file_name) > 417:
        #     continue
        arr = day_quote_to_np(k, SECURITY_TYPE.STOCK)
        if arr is None:
            continue
        logger.info("security day quote:"+ k)
        dtdb.append(k,arr)
    #index
    for k in inlist:
        file_name = GetFileName(k)
        if int(file_name) >= 880001:
            continue
        # if int(file_name) <= 31:
        #     continue
        arr = day_quote_to_np(k, SECURITY_TYPE.INDEX)
        if arr is None:
            continue
        logger.info("security day quote:"+k)
        dtdb.append(k,arr)

import click
@click.command()
@click.option('--day_path', default="E:/buddles/day", help='day bar data path.')
@click.option('--min_path', default='E:/buddles/min',help='min bar data path.')
def data_persist(day_path,min_path):
    day_quote_to_buddle(day_path)
    min_quote_to_buddle(min_path)

def main():
    # stock_list,index_list = get_securities()
    # print(len(stock_list))

    # df = get_index_kline("000001.XSHG", 480)
    # print(df["datetime"])
    pass

if __name__ == "__main__":
    data_persist()