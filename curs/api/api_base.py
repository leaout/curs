from curs.real_quote import *
from curs.cursglobal import *
from curs.const import *

def all_instruments(type=None, date=None):
    '''

    :param type:
    :param date:
    :return:
    '''
    gl = CursGlobal.get_instance()

    if date is None:
        date = gl.real_dt
    if type is None:
        return None

    if type == SECURITY_TYPE.STOCK:
        return gl.stock_map.keys()
    elif type == SECURITY_TYPE.INDEX:
        return gl.index_map.keys()


def get_period_int(frequency):
    if frequency[1] == "m" or frequency[1] == "M":
        if frequency[0] == "5":
            return 5 * 60
        elif frequency[0] == "15":
            return 15 * 60
        elif frequency[0] == "30":
            return 30 * 60
        elif frequency[0] == "60":
            return 60 * 60
    else:
        if frequency[0] == "5":
            return 5 * (24*60*60)
        elif frequency[0] == "15":
            return 15 * (24*60*60)
        elif frequency[0] == "30":
            return 30 * (24*60*60)
        elif frequency[0] == "60":
            return 60 * (24*60*60)
    return 1

def history_bars(order_book_id, bar_count, frequency="1m", fields=None):
    '''

    :param order_book_id:
    :param bar_count:
    :param frequency:
    :param fields:
    :return:
    '''
    buddle_manager = None
    gl = CursGlobal.get_instance()
    ismin = False

    if frequency[1] == "m" or frequency[1]  == "M":
        buddle_manager = gl.min_buddles
        ismin = True
    else:
        buddle_manager = gl.day_buddles

    buddle = buddle_manager.get_buddle(order_book_id)
    if buddle is None:
        return None
    if order_book_id not in gl.stock_map.keys():
        return None
    np_arr = None
    if ismin:
        real_min = gl.stock_map[order_book_id]["1m"]
        sub_counts = bar_count - len(real_min)
        if sub_counts <= 0:
            return real_min
        else:
            sub_counts += 1
            # print(len(buddle[-sub_counts:-1]))
            np_arr = np.concatenate([buddle[-sub_counts:-1], real_min])
    else:
        np_arr = buddle[-bar_count:-1]

    ret_df = pd.DataFrame(np_arr)
    ret_df.columns = pd_names

    ret_df['time'] = ret_df['time'].map(lambda s: (s - s%get_period_int(frequency)))

    ret_df['time'] = ret_df['time'].map(unix_to_timestamp)
    ret_df = ret_df.set_index("time")
    ret_df.index = pd.to_datetime(ret_df.index)
    # ohlc_dict = {
    #     'open': 'first',
    #     'high': 'max',
    #     'low': 'min',
    #     'close': 'last',
    #     'volume': 'sum',
    #     'money': 'sum'
    # }
    # if frequency[0] == "5" :
    #     # ret_df = ret_df.resample('5Min', how=ohlc_dict, closed='left', label='left')
    #     # ret_df = ret_df.resample('5Min').ohlc()
    #     ret_df = ret_df.groupby("time").agg({'low': lambda s: s.min(),
    #                                     'high': lambda s: s.max(),
    #                                     'open': lambda s: s[0],
    #                                     'close': lambda s: s[-1],
    #                                     'volume': lambda s: s.sum(),
    #                                     'money': lambda s: s.sum()})
    ret_df = ret_df.groupby("time").agg({'low': lambda s: s.min(),
                                         'high': lambda s: s.max(),
                                         'open': lambda s: s[0],
                                         'close': lambda s: s[-1],
                                         'volume': lambda s: s.sum(),
                                         'money': lambda s: s.sum()})

    # ret_df.dropna(axis=0, how='any', inplace=True)
    return ret_df




def subscribe_min(order_book_id):
    '''

    :param order_book_id:
    :return:
    '''
    q_engine = QuoteEngine.get_instance()
    q_engine.add_min_subcriber(order_book_id)


if __name__ == "__main__":
    m5_data = history_bars("000001.XSHE", 480, "5m")
    print(m5_data)
    pass
