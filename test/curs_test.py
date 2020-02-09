# coding: utf-8
from curs.real_quote import *
from curs.data_source import *
from curs.utils import *
import tushare as ts
import csv
import pandas as pd
x = 10
def test_eval():
    y = 20  # 局部变量y
    c = eval("x+y", {"x": 1, "y": 2}, {"y": 3, "z": 4})
    print("c:", c)

def ts_to_csv():
    stock_data = ts.get_stock_basics()
    # stock_data.to_csv('stock.csv',columns=['name'])

    stock_edges = pd.DataFrame(columns=['fromID', 'toID', 'type'])

    block_nodes = {}
    begin_code = int(900001);
    # industry
    block_industry = ts.get_industry_classified()
    for row in block_industry.iterrows():
        if row[1]['c_name'] not in block_nodes:
            block_nodes[row[1]['c_name']] = begin_code
            begin_code += 1
        stock_edges = stock_edges.append({'fromID': row[1]['code'], 'toID': str(block_nodes[row[1]['c_name']]), 'type': '属于'},
                                             ignore_index=True)

    # block_industry.to_csv('block_industry.csv',index=None)
    # concept
    block_concept = ts.get_concept_classified()
    for row in block_concept.iterrows():
        if row[1]['c_name'] not in block_nodes:
            block_nodes[row[1]['c_name']] = begin_code
            begin_code += 1
        stock_edges = stock_edges.append({'fromID': row[1]['code'], 'toID': str(block_nodes[row[1]['c_name']]), 'type': '属于'}, ignore_index=True)

    # block_concept.to_csv('block_concept.csv',index=None)

    # area
    block_area =ts.get_area_classified()
    for row in block_area.iterrows():
        if row[1]['area'] not in block_nodes:
            block_nodes[row[1]['area']] = begin_code
            begin_code += 1

        stock_edges = stock_edges.append({'fromID': row[1]['code'], 'toID': str(block_nodes[row[1]['area']]), 'type': '属于'}, ignore_index=True)


    # block_area.to_csv('block_area.csv',index=None)
    # print(stock_edges)
    stock_edges.to_csv('stock_edges.csv',index=None, encoding="utf-8");
    #to csv
    # 1. 创建文件对象
    block_df = pd.DataFrame(columns=['code', 'name'])
    for k,v in block_nodes.items():
        # print(k)
        block_df = block_df.append({'code': str(v), 'name': k}, ignore_index=True)


    block_df = block_df.set_index('code')
    block_df = block_df.append(stock_data)
    block_df.to_csv('stock_nodes.csv',columns=['name'], encoding="utf-8")

def convert_gbk2utf8(file_name):

    gbk_dat = open(file_name, "r", encoding="gbk")
    utf8_dat = open(file_name+".utf8", "w", encoding="utf-8")
    for line in gbk_dat.readlines():
        utf8_dat.write(line)

    utf8_dat.close()
    gbk_dat.close()

def gbk_to_utf8(source, target):
    with open(source, "r", encoding="gbk") as src:
        with open(target, "w", encoding="utf-8") as dst:
            for line in src.readlines():
                dst.write(line)

def block_to_graph():

    pass
def main():
    #
    # carr = bcolz.carray(rootdir="E:/buddles/min/000001.XSHE",  mode="a")
    # print(carr)
    ts_to_csv()

    pass

if __name__ == "__main__":
    main()
