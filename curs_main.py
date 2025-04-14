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

# Web路由
@app.route('/strategies')
def strategies():
    """策略页面"""
    return render_template('strategy.html')

@app.route('/api/strategies')
def api_strategies():
    """获取所有策略信息"""
    strategies = get_all_strategies()
    return strategies

@app.route('/api/strategies/<strategy_id>')
def api_strategy(strategy_id):
    """获取单个策略信息"""
    strategy_info = get_strategy_info(strategy_id)
    return strategy_info

@app.route('/strategy/<strategy_id>/start', methods=['POST'])
def start_strategy(strategy_id):
    """启动策略"""
    try:
        if strategy_manager.start_strategy(strategy_id):
            return {'status': 'success', 'message': '策略已启动'}
        return {'status': 'error', 'message': '策略启动失败'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

@app.route('/strategy/<strategy_id>/stop', methods=['POST'])
def stop_strategy(strategy_id):
    """停止策略"""
    try:
        if strategy_manager.stop_strategy(strategy_id):
            return {'status': 'success', 'message': '策略已停止'}
        return {'status': 'error', 'message': '策略停止失败'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

def get_all_strategies():
    """获取所有策略信息"""
    strategies = []
    strategies_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'strategies')
    for filename in os.listdir(strategies_dir):
        if filename.endswith('.py') and filename != '__init__.py':
            strategy_id = filename[:-3]
            strategy_info = get_strategy_info(strategy_id)
            strategies.append(strategy_info)
    return {'strategies': strategies}

def get_strategy_info(strategy_id):
    """获取策略详细信息"""
    data_file = os.path.join(create_data_dir(), f'{strategy_id}_trades.json')
    if os.path.exists(data_file):
        with open(data_file, 'r', encoding='utf-8') as f:
            trades = json.load(f)
    else:
        trades = []
    
    total_trades = len(trades)
    success_trades = sum(1 for trade in trades if trade.get('success', False))
    success_rate = success_trades / total_trades * 100 if total_trades > 0 else 0
    
    return {
        'id': strategy_id,
        'name': strategy_id.replace('_', ' ').title(),
        'description': f'{strategy_id} strategy description',
        'returns': f'{success_rate:.2f}%',
        'details': f'Total trades: {total_trades}, Success rate: {success_rate:.2f}%',
        'return_curve': [trade.get('profit', 0) for trade in trades[-30:]],
        'holdings': [],
        'positions': trades
    }

def run_flask():
    """运行Flask应用"""
    app.run(host='0.0.0.0', port=8080)

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
    
    # 启动Flask应用
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
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
