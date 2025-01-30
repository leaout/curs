from random import randrange
import os
import csv
from datetime import datetime

from flask import Flask, request, render_template_string, render_template, url_for, redirect
import pandas as pd
import requests

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
    # 假设我们有一个函数来获取所有策略
    strategies = get_all_strategies()
    # 计算每条持仓的收益
    for position in strategies['positions']:
        position['profit'] = (position['current_price'] - position['cost']) * position['quantity']
    return render_template('strategy.html', strategy=strategies)

@app.route('/strategy/<strategy_id>')
def strategy(strategy_id):
    # 假设我们有一个函数来获取单个策略的详细信息
    strategy_info = get_strategy_info(strategy_id)
    return render_template('strategy.html', strategy=strategy_info)

def get_all_strategies():
    # 这里应该从数据库或其他数据源获取所有策略
     return {
        'positions': [
            {'date': '2024-01-01', 'symbol': 'AAPL', 'cost': 150.0, 'quantity': 10, 'current_price': 160.0},
            {'date': '2024-02-01', 'symbol': 'GOOGL', 'cost': 2800.0, 'quantity': 5, 'current_price': 2700.0},
            # Add more positions as needed
        ]
    }

def get_strategy_info(strategy_id):
    # 获取策略基本信息
    strategy_info = {
        'id': strategy_id,
        'name': 'Strategy A',
        'description': 'Description of Strategy A',
        'returns': '10%',
        'details': 'Detailed information about Strategy A',
        'return_curve': [0.05, 0.10, 0.15, 0.20, 0.25],  # Example return curve data
        'holdings': [
            {'symbol': 'AAPL', 'quantity': 100, 'value': 15000},
            {'symbol': 'GOOGL', 'quantity': 50, 'value': 75000}
        ],  # Example holdings data
        'positions': get_strategy_positions(strategy_id)  # 添加持仓历史
    }
    
    # 记录当前持仓到CSV
    for holding in strategy_info['holdings']:
        record_strategy_position(
            strategy_id=strategy_id,
            date=datetime.now().strftime('%Y-%m-%d'),
            symbol=holding['symbol'],
            cost=holding['value'] / holding['quantity'],
            quantity=holding['quantity']
        )
    
    return strategy_info

if __name__ == "__main__":
    app.run()
