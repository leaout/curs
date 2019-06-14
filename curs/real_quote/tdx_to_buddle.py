# coding=utf-8

from curs.real_quote import *
from curs.data_source import *
from curs.utils import *


def day_quote_to_np(code, type):
    '''
    获取当日分钟线
    type index stock
    :param code:"600004.XSHG"
    :return: 返回 np.array
    '''
    if type == "stock":
        df = get_security_kline(code, 240)
    elif type == "index":
        df = get_index_kline(code, 240)
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

    stocklist = stockdf.index.tolist()
    flist = []
    for k in stocklist:
        market = "XSHG" if (k[1] == "sh") else "XSHE"
        bookid = k[0] + '.' + market
        flist.append(bookid)

    return flist

@function_eleapsed
def quote_to_buddle(root_dir):
    dtdb = DataBuddle(root_dir,'a')
    dtdb.open()
    slist,inlist = get_securities()
    for k in slist:
        file_name = GetFileName(k)
        if int(file_name) <= 417:
            continue
        arr = day_quote_to_np(k, "stock")
        if arr is None:
            continue
        print(k)
        dtdb.append(k,arr)
    #index
    for k in inlist:
        file_name = GetFileName(k)
        if int(file_name) >= 880001:
            continue
        arr = day_quote_to_np(k, "index")
        if arr is None:
            continue
        print(k)
        dtdb.append(k,arr)

def main():
    quote_to_buddle("E:/buddles/min")
    # df = get_index_kline("000001.XSHG", 480)
    # print(df["datetime"])
    pass

if __name__ == "__main__":
    main()