# coding: utf-8
from pytdx.reader import BlockReader
import tushare as ts

def tdx_block_reader():
    #指数版块
    df = BlockReader().get_df("C:/new_tdx/T0002/hq_cache/block_zs.dat")
    #风格版块
    df = BlockReader().get_df("C:/new_tdx/T0002/hq_cache/block_fg.dat")
    print(df)
    #概念版块
    df = BlockReader().get_df("C:/new_tdx/T0002/hq_cache/block_gn.dat")

    # stock_data = ts.get_stock_basics()
    # stock_data.to_csv('stock.csv',columns=['name'])




tdx_block_reader()