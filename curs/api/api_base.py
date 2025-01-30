from curs.core import *
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
            return 5 * (24 * 60 * 60)
        elif frequency[0] == "15":
            return 15 * (24 * 60 * 60)
        elif frequency[0] == "30":
            return 30 * (24 * 60 * 60)
        elif frequency[0] == "60":
            return 60 * (24 * 60 * 60)
    return 1


def judge_period_border(unix_time):
    time_local = time.localtime(unix_time)
    time_str = time.strftime("%H:%M:%S", time_local)
    if time_str == "15:00:00":
        return False
    return True


def history_bars(order_book_id, bar_count, frequency="1m", fields=None):
    '''

    :param order_book_id:
    :param bar_count:
    :param frequency:
    :param fields:
    :return:
    '''
    # try:
    buddle_manager = None
    gl = CursGlobal.get_instance()
    ismin = False

    if frequency[1] == "m" or frequency[1] == "M":
        buddle_manager = gl.min_buddles
        ismin = True
    else:
        buddle_manager = gl.day_buddles

    buddle = buddle_manager.get_buddle(order_book_id)
    if buddle is None:
        return None
    if order_book_id not in gl.stock_map.keys():
        return None
    # 计算bar_count
    bar_count = int(frequency[0]) * bar_count

    np_arr = None
    if ismin:
        real_min = gl.stock_map[order_book_id]["1m"]
        real_len = 0
        if real_min is not None:
            real_len = len(real_min)
        sub_counts = bar_count - real_len
        if sub_counts == 0:
            np_arr = real_min
        elif sub_counts < 0:
            # 只从当天分钟线中取数据
            np_arr = real_min[(real_len - bar_count):]
        else:
            sub_counts += 1

            if real_min is not None:
                np_arr = np.concatenate([buddle[-sub_counts:-1], real_min])
            else:
                np_arr = buddle[-sub_counts:-1]
    else:
        if bar_count >= len(buddle):
            np_arr = buddle[:]
        else:
            np_arr = buddle[-bar_count:-1]

    ret_df = pd.DataFrame(np_arr)
    ret_df.columns = pd_names
    # 同一周期时间 改为相同时间
    period_time = get_period_int(frequency)
    ret_df['time'] = ret_df['time'].map(lambda s: ((s + (period_time - s % period_time)) if judge_period_border(
        s) else s))

    ret_df['time'] = ret_df['time'].map(unix_to_timestamp)

    # index 需要转成 datetime 类型
    ret_df.index = pd.to_datetime(ret_df.index)
    # TODO 15:00 无法归并到前一分钟  Done

    ret_df = ret_df.groupby('time').agg({'open': lambda s: s[0],
                                         'close': lambda s: s[-1],
                                         'high': lambda s: s.max(),
                                         'low': lambda s: s.min(),
                                         'volume': lambda s: s.sum(),
                                         'money': lambda s: s.sum()})

    return ret_df

# except Exception as e:
# logger.error(e)
# return None


def subscribe_min(order_book_id):
    '''

    :param order_book_id:
    :return:
    '''
    q_engine = Engine.get_instance()
    q_engine.add_min_subcriber(order_book_id)


if __name__ == "__main__":
    m5_data = history_bars("000001.XSHE", 480, "5m")
    print(m5_data)
    pass
