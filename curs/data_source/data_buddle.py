# coding: utf-8
from curs.utils import *
import bcolz

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


    def get_buddle(self, order_book_id):
        if order_book_id not in self._data:
            if order_book_id not in self._map_dirs:
                return None
            self._data[order_book_id] = bcolz.carray(rootdir=self._map_dirs[order_book_id], mode=self.mode)
        return self._data[order_book_id]

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
            print(self._map_dirs)
            self._map_dirs[name] = self.root_dir + "/" + name
            self._data[name] = bcolz.carray(array,rootdir=self._map_dirs[name], mode=self.mode)

        else:
            self.get_buddle(name)
            self._data[name].append(array)
        self._data[name].flush()

def main():
    # bt = BuddleTools("H:/indexmincsv","H:/buddles")
    # bt.csv_to_carray()
    dbuddle = DataBuddle("E:\\buddles\\day","r")
    dbuddle.open()
    arr = dbuddle.get_buddle("603520.XSHG")
    ret_df = pd.DataFrame(arr[-100:-1])
    ret_df.columns = ['time', 'open', 'close', 'high', 'low', 'volume', 'money']

    # ret_df['time'] = ret_df['time'].map(lambda s: (s - s%get_period_int(frequency)))

    ret_df['time'] = ret_df['time'].map(unix_to_timestamp)

    print(ret_df)
    # buddle = dbuddle.get_buddle("000012.XSHG")
    # print(buddle)
if __name__ == '__main__':
    main()