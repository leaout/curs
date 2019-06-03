import datetime
import doctest
from functools import lru_cache
import time
import requests


from functools import wraps
def function_eleapsed(func):
    #作为装饰器使用，返回函数执行需要花费的时间
    @wraps(func)
    def wrapper(*args,**kwargs):
        start=time.time()
        result=func(*args,**kwargs)
        end=time.time()
        print(func.__name__,"eleapsed time:",end-start)
        return result
    return wrapper
@function_eleapsed
def test_wrapper():
    print("hello")

if __name__ == "__main__":
    test_wrapper()
    # doctest.testmod()