# coding: utf-8
import datetime
from easyquant.easydealutils.read_csv import *

class DataSource(object):
    #read data from csv
    _names = ["date", "open", "high", "low", "last", "amt", "vol"]
    def __init__(self, path_name):
        self._sh_path_name = path_name + "/sh/day"
        self._sz_path_name = path_name + "/sz/day"
        self._map_security = {}

    def load_kline_data(self):
        sh_list = WalkDir(self._sh_path_name)
        sz_list = WalkDir(self._sz_path_name)
        for sz_security_name in sh_list:
            data = ReadFromCsv(self._names, sz_security_name)
            self._map_security["100" + GetFileName(sz_security_name)] = data

        for sz_security_name in sz_list:
            data = ReadFromCsv(self._names, sz_security_name)
            self._map_security["200" + GetFileName(sz_security_name)] = data

    def get_kline_by_sid(self, sid):
        # print(self._map_security)
        if sid in self._map_security.keys():
            return self._map_security[sid]

    def history_bars(self, instrument, bar_count, frequency, fields, dt,
                     adjust_type='pre'):
        if frequency != '1d':
            raise NotImplementedError

        bars = self.get_kline_by_sid(instrument)

        if bars is None :
            return None

        i = bars['date'].searchsorted(dt, side='right')
        left = i - bar_count if i >= bar_count else 0
        print("i=",i[0],",left=",left[0])
        #i left is type numpy.ndarray
        bars = bars[left[0]:i[0]]

        return bars if fields is None else bars[fields]


#test
def main():
    starttime = datetime.datetime.now()
    ds = DataSource("E:/Yueniu/gitYueniu2019/setup_Tdx_Tools/tdx_kline/kdata")
    ds.load_kline_data()
    price = ds.history_bars('100600000',20,'1d','last','20190111','none')
    print(price)
    # print(ds.get_kline_by_sid('100600000'))

    endtime = datetime.datetime.now()

    print(endtime - starttime)
    pass

if __name__ == '__main__':
    main()