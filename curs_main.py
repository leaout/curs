# coding: utf-8

from math import e
from curs.core.engine import Engine
from curs.utils.config import load_yaml
from curs.cursglobal import *
from curs.strategy import *
from curs.strategy_manager import *
import os
import sys
import subprocess
import signal
import argparse
import time
from flask import Flask, render_template
import threading
import json
import csv

# Flask应用实例
app = Flask(__name__)

# 全局变量
global_instance = None
engine = None
strategy_manager = None

# 信号处理函数
def signal_handler(sig, frame):
    print(f"\n捕获到信号 {sig}，正在退出程序...")
    if engine:
        engine.stop()
    sys.exit(0)

def create_data_dir():
    """创建数据目录"""
    data_dir = 'data/strategy_records'
    os.makedirs(data_dir, exist_ok=True)
    return data_dir

def main():
    global global_instance, engine, strategy_manager
    
    # 创建数据目录
    create_data_dir()
    
    # 事件总线
    event_bus = EventBus()
    event_bus.start()
    
    # 加载配置
    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_file_path = os.path.join(current_dir, "config.yml")
    config = load_yaml(config_file_path)
    
    global_instance = CursGlobal(event_bus, config)
    engine = Engine(event_bus, global_instance)
    strategy_manager = StrategyManager(event_bus)
    
    # 加载策略
    load_strategy(config["base"]["strategy_path"])
    
    # 启动交易引擎
    engine.start()
    
    
    # 信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        while True:
            time.sleep(3)
    except Exception as e:
        print(f"发生异常: {e}")
    finally:
        print("程序已退出。")
        sys.exit(0)

def load_strategy(strategy_path):
    """加载策略"""
    for root, dirs, files in os.walk(strategy_path):
        for file in files:
            if file.endswith(".py"):
                strategy_file_path = os.path.join(root, file)
                StrategyManager.get_instance().unload_strategy(strategy_file_path)
                StrategyManager.get_instance().load_strategy(strategy_file_path)

# 启动程序
def start():
    print("启动程序...")
    process = subprocess.Popen([sys.executable, __file__, 'run'])
    with open('curs_main.pid', 'w') as f:
        f.write(str(process.pid))

def stop():
    print("停止程序...")
    if os.path.exists('curs_main.pid'):
        with open('curs_main.pid', 'r') as f:
            pid = int(f.read())
        try:
            os.kill(pid, signal.SIGTERM)
        except Exception as e:
            print("进程不存在。")
        os.remove('curs_main.pid')
    else:
        print("没有找到运行的进程。")

def restart():
    print("重启程序...")
    stop()
    start()
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="控制程序的启动、停止和重启。")
    parser.add_argument('command', choices=['start', 'stop', 'restart', 'run'], help="控制命令")
    args = parser.parse_args()

    if args.command == 'start':
        start()
    elif args.command == 'stop':
        stop()
    elif args.command == 'restart':
        restart()
    elif args.command == 'run':
        main()
