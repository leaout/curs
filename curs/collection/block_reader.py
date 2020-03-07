# coding: utf-8
from pytdx.reader import BlockReader
import tushare as ts
import pandas as pd

def tdx_block_reader():

    # stock_data = ts.get_stock_basics()
    # stock_data.to_csv('stock.csv',columns=['name'])

    stock_edges = pd.DataFrame(columns=['fromID', 'toID', 'type'])

    block_nodes = {}
    begin_code = int(900001);
    #指数版块
    zs_df = BlockReader().get_df("C:/new_tdx/T0002/hq_cache/block_zs.dat")
    for row in zs_df.iterrows():
        if row[1]['blockname'] not in block_nodes:
            block_nodes[row[1]['blockname']] = begin_code
            begin_code += 1
        stock_edges = stock_edges.append({'fromID': row[1]['code'], 'toID': str(block_nodes[row[1]['blockname']]), 'type': '属于'},
                                             ignore_index=True)

    #风格版块
    fg_df = BlockReader().get_df("C:/new_tdx/T0002/hq_cache/block_fg.dat")
    for row in fg_df.iterrows():
        if row[1]['blockname'] not in block_nodes:
            block_nodes[row[1]['blockname']] = begin_code
            begin_code += 1
        stock_edges = stock_edges.append({'fromID': row[1]['code'], 'toID': str(block_nodes[row[1]['blockname']]), 'type': '属于'}, ignore_index=True)


    #概念版块
    gn_df = BlockReader().get_df("C:/new_tdx/T0002/hq_cache/block_gn.dat")
    for row in gn_df.iterrows():
        if row[1]['blockname'] not in block_nodes:
            block_nodes[row[1]['blockname']] = begin_code
            begin_code += 1

        stock_edges = stock_edges.append({'fromID': row[1]['code'], 'toID': str(block_nodes[row[1]['blockname']]), 'type': '属于'}, ignore_index=True)

    # 地区
    block_area =ts.get_area_classified()
    for row in block_area.iterrows():
        if row[1]['area'] not in block_nodes:
            block_nodes[row[1]['area']] = begin_code
            begin_code += 1

        stock_edges = stock_edges.append({'fromID': row[1]['code'], 'toID': str(block_nodes[row[1]['area']]), 'type': '属于'}, ignore_index=True)

    # 行业
    block_industry = ts.get_industry_classified()
    for row in block_industry.iterrows():
        if row[1]['c_name'] not in block_nodes:
            block_nodes[row[1]['c_name']] = begin_code
            begin_code += 1
        stock_edges = stock_edges.append({'fromID': row[1]['code'], 'toID': str(block_nodes[row[1]['c_name']]), 'type': '属于'},
                                             ignore_index=True)
    #edges to csv
    stock_edges.to_csv('stock_edges.csv',index=None, encoding="utf-8");

    # nodes to csv
    stock_data = ts.get_stock_basics()
    nodes_df = pd.DataFrame(columns=['code', 'name'])
    for k,v in block_nodes.items():
        # print(k)
        nodes_df = nodes_df.append({'code': str(v), 'name': k}, ignore_index=True)


    nodes_df = nodes_df.set_index('code')
    nodes_df = nodes_df.append(stock_data)
    nodes_df.to_csv('stock_nodes.csv',columns=['name'], encoding="utf-8")

tdx_block_reader()