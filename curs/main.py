# coding: utf-8
from curs.utils.config import *
from curs.real_quote import *
from curs.cursglobal import *
from curs.strategy import *



def hanle_tick(data):
    s1="603520.XSHG"
    # for k in c_global.stock_map:
    #     print(k)
    quote = g_cursglobal.stock_map[s1]
    print(quote)
def main():
    conf = load_yaml("config.yml")
    print(conf)
    q_engine = QuoteEngine(g_event_bus, g_cursglobal)
    q_engine.start()

    #load strategy
    str = "E:/Quant.Pro/curs/curs/strategy/test_strategy.py"
    load_strategy(str)
    # print(quotes)
    # data = load_yaml("config.yml")
    # print (data["base"])
    while 1 :
        time.sleep(3)
    pass


def load_strategy(strategy_path):
    s_loader = FileStrategyLoader(strategy_path)
    scop = {}
    s_loader.load(scop)
    strategy_context = StrategyContext()
    strategy = Strategy(g_event_bus, scop, strategy_context)
    strategy.init()


if __name__ == "__main__":
    main()