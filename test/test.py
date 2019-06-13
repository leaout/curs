# coding: utf-8
from curs.real_quote import *
from curs.data_source import *
from curs.utils import *

x = 10
def test_eval():
    y = 20  # 局部变量y
    c = eval("x+y", {"x": 1, "y": 2}, {"y": 3, "z": 4})
    print("c:", c)


def main():
    # df = get_security_kline("600004.XSHG", 100)
    # df = reset_col(df)
    #
    # df['datetime'] = df['datetime'].map(timestamp_to_unix_ext)
    # bt = BuddleTools()
    # nparr = bt.df_to_np(df)
    # bt.df_to_carray(df,"E:/hqfile","600004.XSHG")
    # carr = bcolz.carray(rootdir="E:/hqfile/600004.XSHG",  mode="a")
    # print(carr)
    # carr.append(nparr)
    # carr.flush()
    # print(carr)
    # test_eval()

    #列名 df.columns.values

    sedf = get_security_list()
    selist = sedf.index.tolist()
    flist = []
    for k in selist:
        market =  "XSHG" if (k[1] == "sh") else "XSHE"
        bookid = k[0]+ '.' +market
        flist.append(bookid)

    print(flist)
    # print(selist.index.tolist())
    # inlist = get_security_list("index")
    # print(inlist.columns.values)

if __name__ == "__main__":
    main()