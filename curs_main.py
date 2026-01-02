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
import logging

# Flask应用实例
app = Flask(__name__)

# 全局变量
global_instance = None
engine = None
strategy_manager = None

# 导入行情数据获取函数
from curs.broker.qmt_quote import get_stock_kline_data, get_stock_quote_data
from flask import request, jsonify

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

def check_and_start_qmt():
    """检查QMT是否运行，如果没有则启动"""
    logger = logging.getLogger(__name__)
    try:
        # 检查xtMiniQmt.exe进程是否存在
        result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq xtMiniQmt.exe'], 
                               capture_output=True, text=True, shell=True)
        if result.returncode == 0:
            logger.info("QMT已在运行")
            return True
        
        logger.warning("QMT未运行，尝试启动...")
        # 运行启动脚本 (非阻塞)
        script_path = os.path.join(os.path.dirname(__file__), '../../script/startqmt.bat')
        if os.path.exists(script_path):
            subprocess.Popen([script_path], shell=True)
            logger.info("QMT启动脚本已执行")
            # 等待几秒钟让QMT启动
            time.sleep(10)
            return True
        else:
            logger.error(f"QMT启动脚本不存在: {script_path}")
            return False
    except Exception as e:
        logger.exception(f"检查或启动QMT时出错: {e}")
        return False

def main():
    global global_instance, engine, strategy_manager

    # 检查并启动QMT
    if not check_and_start_qmt():
        logger.error("无法启动QMT，程序退出")
        sys.exit(1)
    
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

    # 启动Flask API服务器（在后台线程中运行）
    def run_flask():
        print("启动Flask API服务器...")
        app.run(host='0.0.0.0', port=5001, debug=False, use_reloader=False)

    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("Flask API服务器已启动，监听端口5001")

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

# ===== 行情数据API路由 =====

@app.route('/api/stock/<stock_code>/kline')
def api_stock_kline(stock_code):
    """获取股票K线数据"""
    try:
        if not is_valid_stock_code(stock_code):
            return jsonify({'error': '无效的股票代码格式'}), 400

        kline_data = get_stock_kline_data(stock_code)
        if kline_data:
            return jsonify(kline_data)
        else:
            return jsonify({'error': '未找到股票数据'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stock/<stock_code>/quote')
def api_stock_quote(stock_code):
    """获取股票当日行情"""
    try:
        if not is_valid_stock_code(stock_code):
            return jsonify({'error': '无效的股票代码格式'}), 400

        quote_data = get_stock_quote_data(stock_code)
        if quote_data:
            return jsonify(quote_data)
        else:
            return jsonify({'error': '未找到股票行情数据'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def is_valid_stock_code(stock_code):
    """验证股票代码格式"""
    import re
    # 支持格式如：000001.SH, 600000.SH, 000001.SZ, 002001.SZ等
    pattern = r'^\d{6}\.(SH|SZ)$'
    return re.match(pattern, stock_code.upper()) is not None

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
