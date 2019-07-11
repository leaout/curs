# coding: utf-8
from curs.utils.config import *
from curs.real_quote import *
from curs.cursglobal import *
from curs.strategy import *


def hanle_tick(data):
    s1="603520.XSHG"
    # for k in c_global.stock_map:
    #     print(k)
    quote = CursGlobal.get_instance().stock_map[s1]
    print(quote)
def main():
    #event
    event_bus = EventBus()
    event_bus.start()
    #buddle
    # min_buddle = DataBuddle("E:\\buddles\\min", "r")
    # min_buddle.open()
    #config
    conf = load_yaml("config.yml")

    cgbl = CursGlobal(event_bus,conf)
    cgbl.load_buddles()
    # cgbl.set_data_source(min_buddle)

    q_engine = QuoteEngine(event_bus, CursGlobal.get_instance())
    q_engine.start()

    #load strategy
    str = "E:/Quant.Pro/curs/curs/strategy/test_strategy.py"
    load_strategy(str, event_bus)
    # print(quotes)
    # data = load_yaml("config.yml")
    # print (data["base"])


    while 1 :
        time.sleep(3)
    pass


def load_strategy(strategy_path, event_bus):
    s_loader = FileStrategyLoader(strategy_path)
    scop = {}
    s_loader.load(scop)
    strategy_context = StrategyContext()
    strategy = Strategy(event_bus, scop, strategy_context)
    strategy.init()


if __name__ == "__main__":
    main()