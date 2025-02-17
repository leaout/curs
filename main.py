# coding: utf-8

from curs.core.engine import Engine
from curs.utils.config import load_yaml
from curs.cursglobal import *
from curs.strategy import *
from curs.strategy_manager import *
import os

def main():
    #event
    event_bus = EventBus()
    event_bus.start()
    #load config
    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_file_path = os.path.join(current_dir, "config.yml")
    config = load_yaml(config_file_path)
    
    global_instance = CursGlobal(event_bus,config)
    
    # engine initialization
    engine = Engine(event_bus, global_instance)
    
    strategy_manager = StrategyManager(event_bus)
    # load strategy
    load_strategy(config["base"]["strategy_path"])
    
    engine.start()
    

    while 1 :
        time.sleep(3)
    pass


def load_strategy(strategy_path):
    #遍历文件夹strategy_path，load strategy
    for root, dirs, files in os.walk(strategy_path):
        for file in files:
            if file.endswith(".py"):
                strategy_file_path = os.path.join(root, file)
                StrategyManager.get_instance().load_strategy(strategy_file_path)


if __name__ == "__main__":
    main()