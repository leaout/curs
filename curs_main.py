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
    """通过QMT账户连接成功作为判断，如果连接不上则执行定时任务"""
    logger = logging.getLogger(__name__)
    try:
        from curs.broker.qmt_account import QmtStockAccount
        from curs.utils.config import load_yaml
        import os

        # 加载配置获取账户信息
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_file_path = os.path.join(current_dir, "config.yml")
        config = load_yaml(config_file_path)

        qmt_path = config["base"]["accounts"]["qmt_path"]
        qmt_account_id = config["base"]["accounts"]["qmt_account_id"]
        qmt_trader_name = config["base"]["accounts"]["qmt_trader_name"]

        # 使用测试连接方法验证QMT账户连接
        connection_success = QmtStockAccount.test_connection(
            path=qmt_path,
            account_id=qmt_account_id,
            trader_name=qmt_trader_name,
            session_id=int(time.time())
        )

        if connection_success:
            logger.info("QMT账户连接成功")
            return True
        else:
            logger.warning("QMT账户连接失败，尝试执行定时任务启动QMT")

            # 多次尝试启动QMT并检测连接
            max_startup_attempts = 3  # 最多尝试启动QMT的次数
            connection_checks_per_startup = 3  # 每次启动后进行几次连接检测
            connection_check_delay = 10  # 每次连接检测间隔秒数

            for startup_attempt in range(max_startup_attempts):
                logger.info(f"QMT启动尝试 {startup_attempt + 1}/{max_startup_attempts}")

                try:
                    # 执行定时任务启动QMT
                    logger.info("执行QMT启动定时任务...")
                    schtasks_cmd = 'schtasks /run /tn start_qmt'
                    result = subprocess.run(schtasks_cmd, shell=True, capture_output=True, text=True)

                    if result.returncode != 0:
                        logger.error(f"执行定时任务失败: {result.stderr}")
                        continue  # 尝试下一次启动

                    logger.info("QMT启动定时任务执行成功")

                    # 在启动后进行多次连接检测
                    for check_attempt in range(connection_checks_per_startup):
                        logger.info(f"等待QMT启动后检测连接 (检测 {check_attempt + 1}/{connection_checks_per_startup})...")
                        time.sleep(connection_check_delay)

                        # 重新检测连接
                        retry_connection = QmtStockAccount.test_connection(
                            path=qmt_path,
                            account_id=qmt_account_id,
                            trader_name=qmt_trader_name,
                            session_id=int(time.time()) + startup_attempt * 10 + check_attempt  # 使用不同的session_id避免冲突
                        )

                        if retry_connection:
                            logger.info("QMT账户连接检测成功")
                            return True

                        logger.warning(f"QMT连接检测失败 (检测 {check_attempt + 1}/{connection_checks_per_startup})")

                    logger.warning(f"QMT启动尝试 {startup_attempt + 1} 后连接仍然失败")

                except Exception as task_e:
                    logger.exception(f"QMT启动尝试 {startup_attempt + 1} 时出错: {task_e}")

            logger.error(f"经过 {max_startup_attempts} 次启动尝试后QMT连接仍然失败")
            return False

    except Exception as e:
        logger.exception(f"QMT连接检查时出错: {e}")
        # 如果连接失败，执行已创建的定时任务
        try:
            logger.info("执行QMT启动定时任务...")
            schtasks_cmd = 'schtasks /run /tn start_qmt'
            result = subprocess.run(schtasks_cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                logger.info("QMT启动定时任务执行成功")
                # 等待一段时间让QMT启动
                time.sleep(15)
                return True
            else:
                logger.error(f"执行定时任务失败: {result.stderr}")
        except Exception as task_e:
            logger.exception(f"执行定时任务时出错: {task_e}")
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
