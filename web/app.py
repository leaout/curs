from random import randrange
import os
import csv
import json
from datetime import datetime
from flask import Flask, request, render_template_string, render_template, url_for, redirect
import pandas as pd
import requests
import sys
import os
# 将项目根目录添加到PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# from curs.strategy.strategy_loader import StrategyManager

app = Flask(__name__)

# 创建data目录用于存储CSV文件
DATA_DIR = 'data/strategy_records'
os.makedirs(DATA_DIR, exist_ok=True)

def record_strategy_position(strategy_id, date, symbol, cost, quantity):
    """记录策略持仓信息到CSV文件"""
    filename = f'{DATA_DIR}/strategy_{strategy_id}.csv'
    file_exists = os.path.isfile(filename)
    
    with open(filename, 'a', newline='') as csvfile:
        fieldnames = ['date', 'symbol', 'cost', 'quantity']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        if not file_exists:
            writer.writeheader()
            
        writer.writerow({
            'date': date,
            'symbol': symbol,
            'cost': cost,
            'quantity': quantity
        })

def get_strategy_positions(strategy_id):
    """从CSV文件读取策略持仓历史"""
    filename = f'{DATA_DIR}/strategy_{strategy_id}.csv'
    if not os.path.isfile(filename):
        return []
        
    positions = []
    with open(filename, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            positions.append(row)
    return positions

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

@app.route('/strategy/<strategy_id>')
def strategy(strategy_id):
    """获取单个策略详细信息"""
    strategy_info = get_strategy_info(strategy_id)
    return render_template('strategy.html', strategy=strategy_info)

@app.route('/strategy/<strategy_id>/start', methods=['POST'])
def start_strategy(strategy_id):
    """启动策略"""
    try:
        # manager = StrategyManager()
        # if manager.start_strategy(strategy_id):
        #     return {'status': 'success', 'message': '策略已启动'}
        return {'status': 'error', 'message': '策略启动失败'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

@app.route('/strategy/<strategy_id>/stop', methods=['POST'])
def stop_strategy(strategy_id):
    """停止策略"""
    try:
        # manager = StrategyManager()
        # if manager.stop_strategy(strategy_id):
        #     return {'status': 'success', 'message': '策略已停止'}
        return {'status': 'error', 'message': '策略停止失败'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

def get_all_strategies():
    """获取所有策略信息"""
    strategies = []
    # 扫描strategies目录
    strategies_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'strategies')
    for filename in os.listdir(strategies_dir):
        if filename.endswith('.py') and filename != '__init__.py':
            strategy_id = filename[:-3]  # 去掉.py后缀
            strategy_info = get_strategy_info(strategy_id)
            strategies.append(strategy_info)
    return {
        'strategies': strategies
    }

def get_strategy_info(strategy_id):
    """获取策略详细信息"""
    # 读取策略生成的数据文件
    data_file = os.path.join('data/strategy_records', f'{strategy_id}_trades.json')
    if os.path.exists(data_file):
        with open(data_file, 'r', encoding='utf-8') as f:
            trades = json.load(f)
    else:
        trades = []
    
    # 计算策略指标
    total_trades = len(trades)
    success_trades = sum(1 for trade in trades if trade.get('success', False))
    success_rate = success_trades / total_trades * 100 if total_trades > 0 else 0
    
    return {
        'id': strategy_id,
        'name': strategy_id.replace('_', ' ').title(),
        'description': f'{strategy_id} strategy description',
        'returns': f'{success_rate:.2f}%',
        'details': f'Total trades: {total_trades}, Success rate: {success_rate:.2f}%',
        'return_curve': [trade.get('profit', 0) for trade in trades[-30:]],  # 最近30笔交易收益
        'holdings': [],  # 当前持仓
        'positions': trades  # 历史交易记录
    }

if __name__ == "__main__":
    app.run()
