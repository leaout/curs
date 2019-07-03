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



def history_bars(order_book_id, bar_count, frequency, fields=None):
    '''

    :param order_book_id:
    :param bar_count:
    :param frequency:
    :param fields:
    :return:
    '''
    gl = CursGlobal.get_instance()
    buddle_manager = gl.data_source
    buddle = buddle_manager.get_buddle(order_book_id)
    if buddle is None:
        return None
    if order_book_id not in gl.stock_map.keys():
        return None
    real_min = gl.stock_map[order_book_id]["1m"]
    sub_counts = bar_count - len(real_min)
    if sub_counts <= 0:
        return real_min
    else:
        sub_counts+=1
        # print(len(buddle[-sub_counts:-1]))
        return np.concatenate([buddle[-sub_counts:-1], real_min])



def subscribe_min(order_book_id):
    '''

    :param order_book_id:
    :return:
    '''
    q_engine = QuoteEngine.get_instance()
    q_engine.add_min_subcriber(order_book_id)
