# coding: utf-8
from curs.easydealutils import *
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

    def __init__(self, source_dir, dest_dir):
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

    @function_eleapsed
    def open(self):
        list_dirs = WalkSubDir(self.root_dir)
        for dirs in list_dirs:
            key = os.path.basename(str(dirs))
            self._data[key] = bcolz.carray(rootdir=dirs, mode=self.mode)
        # print(self._data.keys())


    def get_buddle(self,name):
        return self._data[name]

    def insert(self,name,array):
        self._data[name] = array

    def append(self,name,array):
        self._data[name].append(array)

def main():
    # bt = BuddleTools("H:/indexmincsv","H:/buddles")
    # bt.csv_to_carray()
    dbuddle = DataBuddle("H:\\buddles","r")
    dbuddle.open()
    buddle = dbuddle.get_buddle("000012.XSHG")
    print(buddle)
if __name__ == '__main__':
    main()