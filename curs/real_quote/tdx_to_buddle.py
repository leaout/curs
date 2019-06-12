# coding=utf-8

from curs.real_quote import *
from curs.data_source import *
from curs.utils import *


def get_quote_to_np(code):
    '''
    获取当日分钟线
    :param code:"600004.XSHG"
    :return: 返回 np.array
    '''
    df = get_security_kline(code, 240)
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

    return (stocklist+indexlist)


def df_to_securitylist(stockdf):

    stocklist = stockdf.index.tolist()
    flist = []
    for k in stocklist:
        market = "XSHG" if (k[1] == "sh") else "XSHE"
        bookid = k[0] + '.' + market
        flist.append(bookid)

    return flist


def quote_to_buddle(root_dir):
    dtdb = DataBuddle(root_dir,'a')
    slist = get_securities()
    for k in slist:
        arr = get_quote_to_np(k)
        dtdb.append(arr)