# coding=utf-8
from pytdx.hq import TdxHq_API
from retrying import retry
import pandas as pd
from curs.log_handler.logger import logger
import datetime

server_list = [
        # added 20190222 from tdx
        {"ip": "119.147.212.81", "port": 7709, "name": "北京行情主站1"},
        #{"ip": "106.120.74.86", "port": 7711, "name": "北京行情主站1"},
        {"ip": "113.105.73.88", "port": 7709, "name": "深圳行情主站"},
        # {"ip": "113.105.73.88", "port": 7711, "name": "深圳行情主站"},
        {"ip": "114.80.80.222", "port": 7711, "name": "上海行情主站"},
        {"ip": "117.184.140.156", "port": 7711, "name": "移动行情主站"},
        {"ip": "119.147.171.206", "port": 443, "name": "广州行情主站"},
        {"ip": "119.147.171.206", "port": 80, "name": "广州行情主站"},
        {"ip": "218.108.50.178", "port": 7711, "name": "杭州行情主站"},
        {"ip": "221.194.181.176", "port": 7711, "name": "北京行情主站2"},
        # origin
        {"ip": "106.120.74.86", "port": 7709},  # 北京
        {"ip": "112.95.140.74", "port": 7709},
        {"ip": "112.95.140.92", "port": 7709},
        {"ip": "112.95.140.93", "port": 7709},
        {"ip": "113.05.73.88", "port": 7709},  # 深圳
        {"ip": "114.67.61.70", "port": 7709},
        {"ip": "114.80.149.19", "port": 7709},
        {"ip": "114.80.149.22", "port": 7709},
        {"ip": "114.80.149.84", "port": 7709},
        {"ip": "114.80.80.222", "port": 7709},  # 上海
        {"ip": "115.238.56.198", "port": 7709},
        {"ip": "115.238.90.165", "port": 7709},
        {"ip": "117.184.140.156", "port": 7709},  # 移动
        {"ip": "119.147.164.60", "port": 7709},  # 广州
        {"ip": "119.147.171.206", "port": 7709},  # 广州
        {"ip": "119.29.51.30", "port": 7709},
        {"ip": "121.14.104.70", "port": 7709},
        {"ip": "121.14.104.72", "port": 7709},
        {"ip": "121.14.110.194", "port": 7709},  # 深圳
        {"ip": "121.14.2.7", "port": 7709},
        {"ip": "123.125.108.23", "port": 7709},
        {"ip": "123.125.108.24", "port": 7709},
        {"ip": "124.160.88.183", "port": 7709},
        {"ip": "180.153.18.17", "port": 7709},
        {"ip": "180.153.18.170", "port": 7709},
        {"ip": "180.153.18.171", "port": 7709},
        {"ip": "180.153.39.51", "port": 7709},
        {"ip": "218.108.47.69", "port": 7709},
        {"ip": "218.108.50.178", "port": 7709},  # 杭州
        {"ip": "218.108.98.244", "port": 7709},
        {"ip": "218.75.126.9", "port": 7709},
        {"ip": "218.9.148.108", "port": 7709},
        {"ip": "221.194.181.176", "port": 7709},  # 北京
        {"ip": "59.173.18.69", "port": 7709},
        {"ip": "60.12.136.250", "port": 7709},
        {"ip": "60.191.117.167", "port": 7709},
        {"ip": "60.28.29.69", "port": 7709},
        {"ip": "61.135.142.73", "port": 7709},
        {"ip": "61.135.142.88", "port": 7709},  # 北京
        {"ip": "61.152.107.168", "port": 7721},
        {"ip": "61.152.249.56", "port": 7709},  # 上海
        {"ip": "61.153.144.179", "port": 7709},
        {"ip": "61.153.209.138", "port": 7709},
        {"ip": "61.153.209.139", "port": 7709},
        {"ip": "hq.cjis.cn", "port": 7709},
        {"ip": "hq1.daton.com.cn", "port": 7709},
        {"ip": "jstdx.gtjas.com", "port": 7709},
        {"ip": "shtdx.gtjas.com", "port": 7709},
        {"ip": "sztdx.gtjas.com", "port": 7709},

        {"ip": "113.105.142.162", "port": 7721},
        {"ip": "23.129.245.199", "port": 7721},
    ]

api = TdxHq_API()
g_connected = False

def connect_server():
    global g_connected
    if g_connected :
        return True
    try:
        for v in server_list:
            g_connected = api.connect(v['ip'], v['port'])
            if g_connected:
                logger.info("tdx_host=%s:%d %s connect succeed", v['ip'], v['port'], v['name'])
                return True
            else:
                logger.info("tdx_host=%s:%d %s connect failed", v['ip'], v['port'], v['name'])
                continue
    except Exception as e:
        logger.error(e)
        return False



def for_sz(code):
    """深市代码分类
    Arguments:
        code {[type]} -- [description]
    Returns:
        [type] -- [description]
    """
    if str(code)[0:2] in ['00', '30', '02']:
        return 'stock_cn'
    elif str(code)[0:2] in ['39']:
        return 'index_cn'
    elif str(code)[0:2] in ['15']:
        return 'etf_cn'
    elif str(code)[0:2] in ['10', '11', '12', '13']:
        # 10xxxx 国债现货
        # 11xxxx 债券
        # 12xxxx 可转换债券
        # 12xxxx 国债回购
        return 'bond_cn'

    elif str(code)[0:2] in ['20']:
        return 'stockB_cn'
    else:
        return 'undefined'

def for_sh(code):
    if str(code)[0] == '6':
        return 'stock_cn'
    elif str(code)[0:3] in ['000', '880']:
        return 'index_cn'
    elif str(code)[0:2] == '51':
        return 'etf_cn'
    # 110×××120×××企业债券；
    # 129×××100×××可转换债券；
    elif str(code)[0:3] in ['129', '100', '110', '120']:
        return 'bond_cn'
    else:
        return 'undefined'
#type stock 股票 index 指数 etf
@retry(stop_max_attempt_number=3, wait_random_min=50, wait_random_max=100)
def get_security_list(type_='stock'):
    if not connect_server() :
        return None
    data = pd.concat(
        [pd.concat([api.to_df(api.get_security_list(j, i * 1000)).assign(sse='sz' if j == 0 else 'sh').set_index(
            ['code', 'sse'], drop=False) for i in range(int(api.get_security_count(j) / 1000) + 1)], axis=0) for j
            in range(2)], axis=0)
    sz = data.query('sse=="sz"')
    sh = data.query('sse=="sh"')

    sz = sz.assign(sec=sz.code.apply(for_sz))
    sh = sh.assign(sec=sh.code.apply(for_sh))

    if type_ in ['stock', 'gp']:
        return pd.concat([sz, sh]).query('sec=="stock_cn"').sort_index().assign(
            name=data['name'].apply(lambda x: str(x)[0:6]))
    elif type_ in ['index', 'zs']:

        return pd.concat([sz, sh]).query('sec=="index_cn"').sort_index().assign(
            name=data['name'].apply(lambda x: str(x)[0:6]))
        # .assign(szm=data['name'].apply(lambda x: ''.join([y[0] for y in lazy_pinyin(x)])))\
        # .assign(quanpin=data['name'].apply(lambda x: ''.join(lazy_pinyin(x))))
    elif type_ in ['etf', 'ETF']:
        return pd.concat([sz, sh]).query('sec=="etf_cn"').sort_index().assign(
            name=data['name'].apply(lambda x: str(x)[0:6]))
    else:
        return data.assign(code=data['code'].apply(lambda x: str(x))).assign(
            name=data['name'].apply(lambda x: str(x)[0:6]))
    # with api.connect(ip, port):
        # data = pd.concat(
        #     [pd.concat([api.to_df(api.get_security_list(j, i * 1000)).assign(sse='sz' if j == 0 else 'sh').set_index(
        #         ['code', 'sse'], drop=False) for i in range(int(api.get_security_count(j) / 1000) + 1)], axis=0) for j
        #         in range(2)], axis=0)
        # sz = data.query('sse=="sz"')
        # sh = data.query('sse=="sh"')
        #
        # sz = sz.assign(sec=sz.code.apply(for_sz))
        # sh = sh.assign(sec=sh.code.apply(for_sh))
        #
        # if type_ in ['stock', 'gp']:
        #     return pd.concat([sz, sh]).query('sec=="stock_cn"').sort_index().assign(
        #         name=data['name'].apply(lambda x: str(x)[0:6]))
        # elif type_ in ['index', 'zs']:
        #
        #     return pd.concat([sz, sh]).query('sec=="index_cn"').sort_index().assign(
        #         name=data['name'].apply(lambda x: str(x)[0:6]))
        #     # .assign(szm=data['name'].apply(lambda x: ''.join([y[0] for y in lazy_pinyin(x)])))\
        #     # .assign(quanpin=data['name'].apply(lambda x: ''.join(lazy_pinyin(x))))
        # elif type_ in ['etf', 'ETF']:
        #     return pd.concat([sz, sh]).query('sec=="etf_cn"').sort_index().assign(
        #         name=data['name'].apply(lambda x: str(x)[0:6]))
        # else:
        #     return data.assign(code=data['code'].apply(lambda x: str(x))).assign(
        #         name=data['name'].apply(lambda x: str(x)[0:6]))
'''
XSHG表示上海证券交易所,XSHE表示深圳证券交易所,CCFX表示中国金融期货交易所,XDCE表示大连商品交易所,XSGE表示上海期货交易所,XZCE表示郑州商品交易
'''
def str_to_tdxtype(code):
    #600000.XSHG
    list = code.split('.')
    if list[1] == 'XSHG' or list[1] == 'xshg':
        return 1,list[0]
    elif list[1] == 'XSHE' or list[1] == 'xshe':
        return 0,list[0]
# def str_to_tdxtype(market):
#     if market == 'sh':
#         return 1
#     elif market == 'sz':
#         return 0

def tdxtype_to_str(market):
    if market == 1:
        return 'XSHG'
    elif market == 0:
        return 'XSHE'

#股票和指数是两个接口
@retry(stop_max_attempt_number=3, wait_random_min=50, wait_random_max=100)
def get_index_kline(code,count, frequence='1min'):
    # code 证券代码 count k线根数 frequence
    if not connect_server() :
        return None
    type_ = ''
    market_code,code = str_to_tdxtype(code)

    # start_date = str(start)[0:10]
    # today_ = datetime.date.today()
    lens = count
    if str(frequence) in ['5', '5m', '5min', 'five']:
        frequence, type_ = 0, '5min'
        # lens = 48 * lens
    elif str(frequence) in ['1', '1m', '1min', 'one']:
        frequence, type_ = 8, '1min'
        # lens = 240 * lens
    elif str(frequence) in ['15', '15m', '15min', 'fifteen']:
        frequence, type_ = 1, '15min'
        # lens = 16 * lens
    elif str(frequence) in ['30', '30m', '30min', 'half']:
        frequence, type_ = 2, '30min'
        # lens = 8 * lens
    elif str(frequence) in ['60', '60m', '60min', '1h']:
        frequence, type_ = 3, '60min'
    elif str(frequence) in ['d', '1d','day']:
        frequence, type_ = 4, 'day'
    elif str(frequence) in ['w', '1w','week']:
        frequence, type_ = 5, 'week'
    elif str(frequence) in ['mon', 'month']:
        frequence, type_ = 6, 'month'
    elif str(frequence) in ['s', 'season']:
        frequence, type_ = 10, 'season'
    elif str(frequence) in ['y', 'year']:
        frequence, type_ = 11, 'year'

    if lens > 20800:
        lens = 20800
    batch_count = 800
    if count < 800:
        batch_count = count
    # with api.connect(ip, port):
    #
    #     data = pd.concat([api.to_df(api.get_security_bars(frequence,
    #         market_code, str(code), (int(lens / 800) - i) * 800, batch_count)) for i in range(int(lens / 800) + 1)], axis=0)
    #     return data
    data = pd.concat([api.to_df(api.get_index_bars(frequence,
                                                      market_code, str(code), (int(lens / 800) - i) * 800, batch_count))
                      for i in range(int(lens / 800) + 1)], axis=0)
    return data


@retry(stop_max_attempt_number=3, wait_random_min=50, wait_random_max=100)
def get_security_kline(code,count, frequence='1min'):
    # code 证券代码 count k线根数 frequence
    if not connect_server() :
        return None
    type_ = ''
    market_code,code = str_to_tdxtype(code)

    # start_date = str(start)[0:10]
    # today_ = datetime.date.today()
    lens = count
    if str(frequence) in ['5', '5m', '5min', 'five']:
        frequence, type_ = 0, '5min'
        # lens = 48 * lens
    elif str(frequence) in ['1', '1m', '1min', 'one']:
        frequence, type_ = 8, '1min'
        # lens = 240 * lens
    elif str(frequence) in ['15', '15m', '15min', 'fifteen']:
        frequence, type_ = 1, '15min'
        # lens = 16 * lens
    elif str(frequence) in ['30', '30m', '30min', 'half']:
        frequence, type_ = 2, '30min'
        # lens = 8 * lens
    elif str(frequence) in ['60', '60m', '60min', '1h']:
        frequence, type_ = 3, '60min'
    elif str(frequence) in ['d', '1d','day']:
        frequence, type_ = 4, 'day'
    elif str(frequence) in ['w', '1w','week']:
        frequence, type_ = 5, 'week'
    elif str(frequence) in ['mon', 'month']:
        frequence, type_ = 6, 'month'
    elif str(frequence) in ['s', 'season']:
        frequence, type_ = 10, 'season'
    elif str(frequence) in ['y', 'year']:
        frequence, type_ = 11, 'year'

    if lens > 20800:
        lens = 20800
    batch_count = 800
    if count < 800:
        batch_count = count
    # with api.connect(ip, port):
    #
    #     data = pd.concat([api.to_df(api.get_security_bars(frequence,
    #         market_code, str(code), (int(lens / 800) - i) * 800, batch_count)) for i in range(int(lens / 800) + 1)], axis=0)
    #     return data
    data = pd.concat([api.to_df(api.get_security_bars(frequence,
                                                      market_code, str(code), (int(lens / 800) - i) * 800, batch_count))
                      for i in range(int(lens / 800) + 1)], axis=0)
    return data
        # data = data \
        #     .drop(['year', 'month', 'day', 'hour', 'minute'], axis=1, inplace=False) \
        #     .assign(datetime=pd.to_datetime(data['datetime']), code=str(code),
        #             date=data['datetime'].apply(lambda x: str(x)[0:10]),
        #             date_stamp=data['datetime'].apply(
        #         lambda x: QA_util_date_stamp(x)),
        #         time_stamp=data['datetime'].apply(
        #         lambda x: QA_util_time_stamp(x)),
        #         type=type_).set_index('datetime', drop=False, inplace=False)[start:end]
        # return data.assign(datetime=data['datetime'].apply(lambda x: str(x)))

@retry(stop_max_attempt_number=3, wait_random_min=50, wait_random_max=100)
def get_security_quotes(list):
    # ['000001.xshe',  '600300.xshg']
    if not connect_server() :
        return None
    s_list = convert_tdx_type(list)
    #长度限制80
    # print("s_list:",len(s_list))
    data = []
    for v in range(0,len(s_list),80):
        qt = api.get_security_quotes(s_list[v:v + 80])
        if qt is not None:
            data += qt

    #to map data
    # print("data",len(data))
    map_data = {}
    if data is None:
        return map_data
    for v in data:
        map_data[v['code'] + '.' + tdxtype_to_str(v['market'])] = v
    return map_data


def convert_tdx_type(list):
    s_list = []
    for v in list:
        code = str_to_tdxtype(v)
        s_list.append(code)
    return s_list


@retry(stop_max_attempt_number=3, wait_random_min=50, wait_random_max=100)
def get_security_trade(code,pos,count):
    '''
        分笔成交
    :param code: 600000.xshg
    :param pos: 0
    :param count: 30
    :return:
    '''
    if not connect_server() :
        return None
    market,code = str_to_tdxtype(code)
    data = api.get_transaction_data(market, code, pos, count)
    #to map data
    return data

@retry(stop_max_attempt_number=3, wait_random_min=50, wait_random_max=100)
def get_security_finance_info(code):
    '''
    读取财务信息
    :param code: 600000.xshg
    :return:
    '''
    if not connect_server() :
        return None
    market, code = str_to_tdxtype(code)
    data = api.get_finance_info(market, code)
    return data

order = ['datetime', 'open', 'close', 'high', 'low', 'vol', 'amount']
def reset_col(data):
    '''
    修改列顺序
    :param data: pandas
    :return:
    '''
    try:
        if data is not None:
            return data[order]
    except Exception as e:
        logger.error(e)
        return None


import datetime
import math
def get_today_kline_counts():

    l_timestr = datetime.datetime.now().strftime('%H-%M-%S').split('-', 3)
    # now_h = datetime.datetime.now().strftime('%H')
    # now_m = datetime.datetime.now().strftime('%M')
    # now_s = datetime.datetime.now().strftime('%S')
    now_h = l_timestr[0]
    now_m = l_timestr[1]
    now_s = l_timestr[2]
    now_time = (now_h + now_m + now_s)
    t930 = datetime.datetime(2001,1,1,9, 30, 00)
    tnow = datetime.datetime(2001,1,1,int(now_h), int(now_m), int(now_s))
    if int(now_time) < 93000:
        return 0
    if int(now_time) >= 150000:
        return 240
    if int(now_time) < 113000:
        return math.ceil((tnow - t930).seconds/60)
    if int(now_time) >= 130000 :
        return math.ceil((tnow - t930).seconds/60) - 90

def main():
    # data = get_security_kline("600446","sh",10)
    # print(data)
    # data = api.get_minute_time_data(1, '600300')
    # data = get_security_kline("600004.xshg", 240)
    # data1 = get_index_kline("000001.xshg", 240)
    # se_list = get_security_list()
    # print(se_list)
    # data = get_security_trade('000001.xshe',0,1)
    # for v in data:
    #     print(v)
    # quote = get_security_quotes(["600000.xshg"])
    # print(quote)
    # data = get_security_finance_info("000001.xshe")
    # print(mins_between(92500,103000))
    # counts = get_today_kline_counts()
    # print(counts)

    print(datetime.datetime.min.time())
    # print(data)
    # print(data1)
    pass
if __name__ == '__main__':
    main()