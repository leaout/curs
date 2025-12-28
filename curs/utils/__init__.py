from .read_csv import *
# from .time import *
# from .cursplot import *
# from .indicator import *
from .stock_validator import *
import numpy as np

def id_gen(start=1):
    i = start
    while True:
        yield i
        i += 1

def is_valid_price(price):
    return not np.isnan(price) and price > 0 and price is not None
