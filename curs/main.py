# coding: utf-8
from curs.utils.config import *
from curs.real_quote import *
from curs.cursglobal import *
from curs.events import *

event_bus = EventBus()
c_global = CursGlobal(event_bus)
def hanle_tick(data):
    s1="603520.XSHG"
    # for k in c_global.stock_map:
    #     print(k)
    quote = c_global.stock_map[s1]
    print(quote)
def main():

    event_bus.start()
    event_bus.add_listener(EVENT.TICK,hanle_tick)


    q_engine = QuoteEngine(event_bus, c_global)
    q_engine.start()


    # print(quotes)
    # data = load_yaml("config.yml")
    # print (data["base"])
    while 1 :
        time.sleep(3)
    pass


if __name__ == "__main__":
    main()