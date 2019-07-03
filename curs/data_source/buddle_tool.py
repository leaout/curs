# coding: utf-8
from curs.utils import *
import bcolz
import numpy as np
from curs.log_handler.logger import logger
from curs.data_source import *

pd_names = ['time', 'open', 'close', 'high', 'low', 'volume', 'money']

class BuddleTools(object):

    def __init__(self, source_dir = None, dest_dir = None):
        self._srcdir = source_dir
        self._dstdir = dest_dir

    def csv_to_carray(self):
        list_csvs = WalkDir(self._srcdir)
        logger.info("totoal counts:",len(list_csvs))
        for csv in list_csvs:
            df = ReadFromCsv(pd_names, csv,1,',')
            # print(df)
            df['time'] = df['time'].map(timestamp_to_unix)
            # print(df)
            arr = np.array(df)
            dst_root = os.path.join(self._dstdir, os.path.basename(csv))
            carr = bcolz.carray(arr, chunklen=100 * 1024, expectedlen=100 * 1024, rootdir=dst_root,
                                 cparams=bcolz.cparams(quantize=1))
            carr.flush()

    def csv_to_nparray(self,src_file):
        try:
            df = ReadFromCsv(pd_names, src_file, 1, ',')
            df['time'] = df['time'].map(timestamp_to_unix)
            # print(df)
            return np.array(df)
        except Exception as e:
            logger.error(e)


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

    @classmethod
    def df_to_np(cls,df):

        return np.array(df)

    def json_to_csv(self, root_dir, dst_dir):
        f_list = WalkDir(root_dir)
        for file in f_list:
            df = pd.read_json(file)
            df.to_csv(dst_dir + "/" + os.path.basename(file))

    @function_eleapsed
    def csv_append_buddle(self, buddle_dir, csv_dir):
        dbuddle = DataBuddle(buddle_dir, "a")
        dbuddle.open()
        csvs = WalkDir(csv_dir)
        for csv in csvs:
            # filename = GetFileName(str(csv))
            # if int(filename) < 399292:
            #     continue
            arr = self.csv_to_nparray(csv)
            key = os.path.basename(str(csv))
            print(key)
            dbuddle.append(key,arr)



def main():
    bt = BuddleTools("H:/mincsv","H:/buddles")

    # bt.json_to_csv("H:/indexmin","H:/indexmincsv")
    # bt.json_to_csv("H:/min", "H:/mincsv")

    # dbuddle = DataBuddle("E:\\buddles","r")
    # dbuddle.open()
    # buddle = dbuddle.get_buddle("000012.XSHG")
    # print(buddle)
    #指数
    bt.csv_append_buddle("E:/buddles/min", "H:/indexmincsv")
    #股票
    bt.csv_append_buddle("E:/buddles/min","H:/mincsv")
    pass

if __name__ == '__main__':
    main()