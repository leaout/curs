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
# 信号处理函数
def signal_handler(sig, frame):
    print(f"\n捕获到信号 {sig}，正在退出程序...")
    sys.exit(0)
    
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
    
    # signal handler
    # 注册信号处理函数
    # signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    # signal.signal(signal.SIGTERM, signal_handler)  # 终止信号
    
    try:
        while True:
            time.sleep(3)  # 模拟程序工作
    except Exception as e:
        print(f"发生异常: {e}")
    finally:
        # 清理资源（如果有）
        print("程序已退出。")
        sys.exit(0)


def load_strategy(strategy_path):
    #遍历文件夹strategy_path，load strategy
    for root, dirs, files in os.walk(strategy_path):
        for file in files:
            if file.endswith(".py"):
                strategy_file_path = os.path.join(root, file)
                StrategyManager.get_instance().unload_strategy(strategy_file_path)
                StrategyManager.get_instance().load_strategy(strategy_file_path)

# 启动程序
def start():
    print("启动程序...")
    # 使用subprocess.Popen启动一个新的进程
    process = subprocess.Popen([sys.executable, __file__, 'run'])
    # 将进程ID写入文件以便后续停止或重启时使用
    with open('curs_main.pid', 'w') as f:
        f.write(str(process.pid))

# 停止程序
def stop():
    print("停止程序...")
    if os.path.exists('curs_main.pid'):
        with open('curs_main.pid', 'r') as f:
            pid = int(f.read())
        # 发送SIGTERM信号终止进程
        try:
            os.kill(pid, signal.SIGTERM)
        except Exception as e:
            print("进程不存在。")
        os.remove('curs_main.pid')
    else:
        print("没有找到运行的进程。")

# 重启程序
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