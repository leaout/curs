# coding: utf-8
from curs.real_quote import *
from curs.data_source import *
from curs.utils import *
import tushare as ts

x = 10
def test_eval():
    y = 20  # 局部变量y
    c = eval("x+y", {"x": 1, "y": 2}, {"y": 3, "z": 4})
    print("c:", c)

def ts_to_csv():
    stock_data = ts.get_stock_basics()
    stock_data.to_csv('stock.csv')

    block_industry = ts.get_industry_classified()
    block_industry.to_csv('block_industry.csv')

    block_concept = ts.get_concept_classified()
    block_concept.to_csv('block_concept.csv')

    block_area =ts.get_area_classified()
    block_area.to_csv('block_area.csv')
def main():
    #
    # carr = bcolz.carray(rootdir="E:/buddles/min/000001.XSHE",  mode="a")
    # print(carr)
    ts_to_csv()

    pass

if __name__ == "__main__":
    main()