# coding=utf-8
from .quote_from_tdx import *
from .tdx_to_buddle import *
from .quote_engine import *
from curs.const import *

def get_security_type(order_book_id):
    '''

    :param order_book_id 600000.XSHG:
    :return:
    '''
    if order_book_id is None:
        return None
    list = order_book_id.split('.')
    if list[1] == "XSHG" and int(list[0]) < 600000:
        return SECURITY_TYPE.INDEX

    if list[1] == "XSHE" and int(list[0]) >= 399001:
        return SECURITY_TYPE.INDEX
    return SECURITY_TYPE.STOCK