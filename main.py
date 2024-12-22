# coding: utf-8

from curs.engine.quote_engine import QuoteEngine
from curs.utils.config import load_yaml
from curs.cursglobal import *
from curs.strategy import *
import os

def main():
    #event
    event_bus = EventBus()
    event_bus.start()
    #获取当前目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_file_path = os.path.join(current_dir, "config.yml")
    config = load_yaml(config_file_path)
    

    global_instance = CursGlobal(event_bus,config)
    
    engine = QuoteEngine(event_bus, global_instance)
    
    load_strategy(current_dir+"/curs/strategy/test_strategy.py", event_bus)
    engine.start()
    

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