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
    dbuddle = DataBuddle("E:\\buddles","r")
    dbuddle.open()
    # buddle = dbuddle.get_buddle("000012.XSHG")
    # print(buddle)
if __name__ == '__main__':
    main()