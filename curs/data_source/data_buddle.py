# coding: utf-8
from curs.utils import *
import bcolz
import numpy as np

# class DataBuddle(object):
#     def __init__(self,root_dir,mode):
#         self.root_dir = root_dir
#         self.mode = mode
#         self._data
#     def open(self):
#         self._data = bcolz.carray(rootdir=self.root_dir, mode=self.mode)
pd_names = ['time', 'open', 'close', 'high', 'low', 'volume', 'money']

class BuddleTools(object):

    def __init__(self, source_dir = None, dest_dir = None):
        self._srcdir = source_dir
        self._dstdir = dest_dir

    def csv_to_carray(self):
        list_csvs = WalkDir(self._srcdir)
        print("totoal counts:",len(list_csvs))
        for csv in list_csvs:
            print(csv)
            df = ReadFromCsv(pd_names, csv,1,',')
            # print(df)
            df['time'] = df['time'].map(timestamp_to_unix)
            # print(df)
            arr = np.array(df)
            dst_root = os.path.join(self._dstdir, os.path.basename(csv))
            carr = bcolz.carray(arr, chunklen=100 * 1024, expectedlen=100 * 1024, rootdir=dst_root,
                                 cparams=bcolz.cparams(quantize=1))
            carr.flush()

    def df_to_carray(self,df, dir, name):
        '''

        :param df: 数据
        :param dir: 目录
        :param name: 名称
        :return: carray
        '''
        arr = np.array(df)
        dst_root = os.path.join(dir, name)
        carr = bcolz.carray(arr, chunklen=100 * 1024, expectedlen=100 * 1024, rootdir=dst_root,
                            cparams=bcolz.cparams(quantize=1))
        return carr

    def df_to_np(self,df):

        return np.array(df)

class DataBuddle(object):
    '''
    root_dir top dir ,include many carrays
    mode r w
    _data  data carrays
    '''
    def __init__(self,root_dir,mode):
        self.root_dir = root_dir
        self.mode = mode
        self._data = {}
        self._map_dirs = {}

    @function_eleapsed
    def open(self):
        '''
        先加载目录，动态加载数据
        :return:
        '''
        list_dirs = WalkSubDir(self.root_dir)
        for dirs in list_dirs:
            key = os.path.basename(str(dirs))
            # self._data[key] = bcolz.carray(rootdir=dirs, mode=self.mode)
            self._map_dirs[key] = dirs
        # print(self._data.keys())


    def get_buddle(self,name):
        if name not in self._data:
            if name not in self._map_dirs:
                return None
            self._data[name] = bcolz.carray(rootdir=self._map_dirs[name], mode=self.mode)
        return self._data[name]

    def insert(self,name,array):
        self._data[name] = array

    def append(self,name,array):
        '''
        add np.array
        :param name:
        :param np.array:
        :return:
        '''
        if name not in self._map_dirs:
            self._map_dirs[name] = self.root_dir + "/" + name
            self._data[name] = bcolz.carray(rootdir=self._map_dirs[name], mode=self.mode)
        else:
            self._data[name].append(array)

def main():
    # bt = BuddleTools("H:/indexmincsv","H:/buddles")
    # bt.csv_to_carray()
    dbuddle = DataBuddle("E:\\buddles","r")
    dbuddle.open()
    buddle = dbuddle.get_buddle("000012.XSHG")
    print(buddle)
if __name__ == '__main__':
    main()