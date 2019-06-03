import numpy as np
from numpy import *
import bcolz
import pandas as pd
import os
import numpy as np
import json
import datetime
import time
# from trading_calendars import get_calendar

# data = bcolz.open(rootdir="D:/rqbuddle/bundle/stocks.bcolz", mode="a" )
# data.where('600000')
# _index=data.attrs['line_map']
# _order_book_id = _index.keys()
# print(_order_book_id)
# data = bcolz.open(rootdir="D:/JoinQuant-Desktop-Py3/USERDATA/.joinquant-py3/bundle/stock1m/00/000100.XSHE", mode="r" )
# data = bcolz.open(rootdir="D:/JoinQuant-Desktop-Py3/USERDATA/.joinquant-py3/bundle/index1m/00/000100.XSHG", mode="r" )
# with open("D:/JoinQuant-Desktop-Py3/USERDATA/.joinquant-py3/bundle/index1m/00/000100.XSHG/meta.json",'r') as load_f:
#      load_dict = json.load(load_f)
#      for k,v in load_dict.items():
#          print(k)
     # print(load_dict)
# print(data)
#  save = data.todataframe()
# save.to_csv('stock.csv')

#read csv

# df1 = pd.read_csv("C:/security_info/security_info.txt", sep=' ',low_memory=False,header=1,encoding="gb2312")
# df1 = pd.read_csv("D:/project/test/stock.csv", sep=',',low_memory=False,header=1)
# df1= df1.dropna(axis=1,how='all')

# bcolz.print_versions()
# bcolz.defaults.cparams['cname'] = 'lz4'
# bcolz.defaults.cparams['clevel'] = 5
#
# bcolz_dir = "movielens-denorm.bcolz"
# if os.path.exists(bcolz_dir):
#     import shutil
#     shutil.rmtree(bcolz_dir)
# zlens = bcolz.ctable.fromdataframe(lens, rootdir=bcolz_dir)
names = ["date", "open", "high", "low", "last", "amt", "vol"]
names1 = ["time", "close", "high", "low", "money", "open", "volume"]

def test_bcolz():
    csv_path = "G:/indexmincsv/000001.XSHG"
    df = pd.read_csv(csv_path, sep=',', encoding="gb2312", names=names1, header=None, skiprows=1)
    # print(df)
    # df.set_index('time')
    print(df)

    bd = bcolz.ctable.fromdataframe(df, rootdir="G:/bcolz")
    # print(df)


def readFromCsv(csv_path):
    df = pd.read_csv(csv_path, sep='\t',names=names,header=None,encoding="gb2312")
    # data = np.array(df)
    df.columns = [''.join(icol.split()) for icol in df.columns.values.tolist()]
    return df

def walkDir(rootdir):
    l_file = []
    list = os.listdir(rootdir)
    for i in range(0, len(list)):
        path = os.path.join(rootdir, list[i])
        if os.path.isfile(path):
            l_file.append(path)
    return l_file
def GetFileName(full_name):
    return os.path.splitext(os.path.basename(full_name))[0]

def readCsv2DataFram():
    list = walkDir("E:/Yueniu/gitYueniu2019/setup_Tdx_Tools/tdx_kline/kdata/sh/day")
    map_data = {}
    for file_name in list:
        data = readFromCsv(file_name)
        map_data[GetFileName(file_name)] = data
    return  map_data

def get_sid_attr(self, sid, name):
    sid_subdir = ""
    sid_path = os.path.join(self._rootdir, sid_subdir)
    attrs = bcolz.attrs.attrs(sid_path, 'r')
    try:
        return attrs[name]
    except KeyError:
        return None

# test carray
# your_data= [1,2,3,4]
# path = 'E:\\test.carray'
# bcolz_array = bcolz.carray(np.zeros([0,3,128,128], dtype=np.float32), mode='w', rootdir=path)
# for x in your_data:
#     bcolz_array.append(x)

# bcolz_array.flush()

'''
# 1.把datetime转成字符串
def datetime_toString(dt):
    print("1.把datetime转成字符串: ", dt.strftime("%Y-%m-%d %H:%M:%S"))
# 2.把字符串转成datetime
def string_toDatetime(st):
    print("2.把字符串转成datetime: ", datetime.datetime.strptime(st, "%Y-%m-%d %H:%M:%S"))
# 3.把字符串转成时间戳形式
def string_toTimestamp(st):
    print("3.把字符串转成时间戳形式:", time.mktime(time.strptime(st, "%Y-%m-%d %H:%M:%S")))
# 4.把时间戳转成字符串形式
def timestamp_toString(sp):
    print("4.把时间戳转成字符串形式: ", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(sp)))
# 5.把datetime类型转外时间戳形式
def datetime_toTimestamp(dt):
    print("5.把datetime类型转外时间戳形式:", time.mktime(dt.timetuple()))
'''

#
dtype={
        'names': (
                   'time', 'open', 'close',
                   'high', 'low', 'volume', 'money'),
               'formats': (
                   '|S20', np.float, np.float, np.float, np.float, np.int, np.int)}
def timestamp_to_unix(time_stamp):
    a = datetime.datetime.strptime(str(time_stamp), "%Y-%m-%d %H:%M:%S").timetuple()
    b = time.mktime(a)
    return int(b)
    # return datetime.datetime.strptime(str(time_stamp), "%Y-%m-%d %H:%M:%S")

def byte_to_str(b):
    return str(b, encoding="utf8")

pd_names = ['time', 'open', 'close', 'high', 'low', 'volume', 'money']
def ReadFromCsv(names, csv_path):
    df = pd.read_csv(csv_path, sep=',', names=names, header=None, encoding="gb2312",skiprows=1)
    # data = np.array(df)
    #df.columns = [''.join(icol.split()) for icol in df.columns.values.tolist()]
    return df
def test_carray():
    # a = np.arange(1e7)
    # carr = bcolz.carray(a)
    # # print(carr)
    # # print(carr.chunklen)
    #
    # carr1 = bcolz.carray(a, chunklen=512)
    # carr2 = bcolz.carray(a, chunklen=8 * 1024)
    #
    # print(carr1.chunklen)
    # print(carr2.chunklen)
    #np.genfromtxt('data.txt', delimiter=',', dtype=None, names=('sepal length', 'sepal width', 'petal length', 'petal width', 'label')) ,converters={0:timestamp_to_unix}
    # arr = np.loadtxt("D:/quote/csv/000001.XSHE",skiprows=1, delimiter=',',dtype=dtype,converters={0:byte_to_str} )
    # type(arr[0])

    # arr22 = arr['time'].astype(str)
    # arr22 = arr[:,1].astype(str)
    # arr23 = arr['open']
    # print(arr22.T)
    # arr25 = np.hstack((arr22, arr23))
    # print(arr25)
    # print(arr['time'].dtype)

    # df = ReadFromCsv(pd_names,"D:/quote/csv/000001.XSHE")
    # df['time'] = df['time'].map(timestamp_to_unix)
    # # # print(df)
    # arr = np.array(df)
    # # print(arr)
    # print(timestamp_to_unix("2005-01-04 09:32:00"))
    # # print(arr[:,0])
    # carr3 = bcolz.carray(arr, chunklen=1024 * 1024,expectedlen=1024*1024,rootdir="D:/quote/000001.XSHE1",cparams=bcolz.cparams(quantize=1))
    # carr3.flush()
    key = os.path.basename('H:/buddles\\000001.XSHE')
    carr31 = bcolz.carray(rootdir="H:/buddles\\000001.XSHE",mode='r')
    print(carr31)
    #np read csv to carray  flush to disk



if __name__ == "__main__":
    #load data from txt
    # print(GetFileName("11/111111/0000001.txt"))
    # map_data = readCsv2DataFram()
    # print(map_data)
    # rootdir="E:/test.bcolz"
    #行列转换
    # col_data= map_data["000001.txt"].values.T

    # print(len(mat(col_data).T))

    # print(mat(col_data))

    # print(len(type(col_data)))
    # print(len(map_data["000001.txt"]))
    # test for ctable
    # print(col_data.shape)
    # print( hasattr(col_data.dtype, "names"))
    # ctbl = bcolz.ctable(col_data.tolist(), names=names, rootdir=rootdir, mode='w')
    # ctbl.flush()

    #test for carray\
    # a = bcolz.zeros((2, 3))
    # c = bcolz.carray(a, rootdir='E:/carray.bcolz')
    # c.flush()

    # tradingcalendar
    # china_calendar = get_calendar('XSHG')
    # print(china_calendar)
    test_carray()
    print(1111111111111)

    pass