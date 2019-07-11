from curs.log_handler.logger import logger
from curs.cursglobal import *
from curs.api import *
import matplotlib.pyplot as plt
#test
from curs.api import *
from curs.utils import *

# 在这个方法中编写任何的初始化逻辑。context对象将会在你的算法策略的任何方法之间做传递。
def init(context):
    logger.info("init")
    context.s1 = "000001.XSHE"
    subscribe_min(context.s1)
    # QuoteEngine.add_min_subcriber("000001.XSHE")

def before_trading(context):
    pass


# 你选择的证券的数据更新将会触发此段逻辑，例如日或分钟历史数据切片或者是实时数据切片更新
def handle_bar(context, bar_dict):
    # 开始编写你的主要的算法逻辑

    # bar_dict[order_book_id] 可以拿到某个证券的bar信息
    # context.portfolio 可以拿到现在的投资组合状态信息

    # 使用order_shares(id_or_ins, amount)方法进行落单

    # TODO: 开始编写你的算法吧！
    if not context.fired:
        # order_percent并且传入1代表买入该股票并且使其占有投资组合的100%
        context.fired = True


def handle_tick(context,tick):
    logger.info("handle_tick")
    s1="603520.XSHG"
    # for k in c_global.stock_map:
    #     print(k)
    m1_data = history_bars(context.s1,20,"5m")
    if m1_data is None:
        return
    logger.info(m1_data.close)
    # m1_data["close"].plot(kind='line')
    # plt.show()
    logger.info("len:%d"%len(m1_data))
    logger.info(m1_data.columns)

    logger.info("Now time:"+CursGlobal.get_instance().real_dt.strftime("%Y-%m-%d %H:%M:%S"))
    logger.info(CursGlobal.get_instance().stock_map[context.s1]["quote"])

    # m5_data = history_bars("000001.XSHE", 20, "5m")
    # candles_plot(m5_data,"000001.XSHE")