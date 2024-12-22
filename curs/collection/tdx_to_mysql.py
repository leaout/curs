# coding: utf-8

import datetime
from curs.engine.quote_from_tdx import *
from sqlalchemy import Column,Integer,String
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine,BIGINT,MetaData,Table
from sqlalchemy.ext.declarative import declarative_base

# stock_df = get_security_list('stock')
# for index, row in stock_df.iterrows():
#     print(row['code'],row['sse'])
#
# index_df = get_security_list('index')
# for index, row in index_df.iterrows():
#     print(row['code'],row['sse'])
#
# data = get_security_kline('600000','sh',10, frequence='day')
# print(data.columns)
base = declarative_base() #创建基类
class table_kline(base):
    __tablename__ = 'tdx_kline'
    security_id = Column(Integer, primary_key=True)
    trans_date = Column( Integer)
    pre_close_px = Column(Integer)
    open_px = Column(Integer)
    high_px = Column(Integer)
    low_px = Column(Integer)
    last_px = Column(Integer)
    volume = Column(BIGINT)
    value = Column(BIGINT),

def create_kline_table():
    metadata = MetaData()
    table_kline = Table('tdx_kline', metadata,
                 Column('security_id', Integer, primary_key=True),
                 Column('trans_date', Integer),
                 Column('pre_close_px', Integer),
                 Column('open_px', Integer),
                 Column('high_px', Integer),
                 Column('low_px', Integer ),
                 Column('last_px', Integer),
                 Column('volume', BIGINT),
                 Column('value', BIGINT),
                 )
    return table_kline
def insert_kline_batch(df,engine):
    #df 数据
    # 寻找Base的所有子类，按照子类的结构在数据库中生成对应的数据表信息
    base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
def insert_kline(df,table_kline):
    pass
def main():
    #获取股票代码表
    stock_df = get_security_list('stock')
    print(stock_df.index)
    # #获取指数代码表
    # index_df = get_security_list('index')
    # # 初始化数据库连接，使用pymysql模块
    engine = create_engine('mysql+pymysql://root@localhost:3306/tdxdb')
    #
    # for index, row in stock_df.iterrows():
    #     sid = 0
    #     if row['sse'] =='sh':
    #         sid = 100000000+ int(row['code'])
    #     else:
    #         sid = 200000000 + int(row['code'])
    #     df = get_security_kline(row['code'], row['sse'], 10, frequence='day')
    #     df['sid'] = sid
    #     df.set_index('sid', inplace=True)
    #     # print(df)
    #     df.to_sql('tdx_df_kline',engine,if_exists='append')
    # table_kline = create_kline_table()
    # conn = engine.connect()
    # sql = table_kline.insert().values(security_id=100600000,trans_date=20190402)
    # conn.execute(sql)
    # conn.close()

if __name__=="__main__":
    main()