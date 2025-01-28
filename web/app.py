from random import randrange

from flask import Flask, request, render_template_string, render_template, url_for, redirect
import pandas as pd
import requests
import datetime

app = Flask(__name__)

@app.route('/strategies')
def strategies():
    # 假设我们有一个函数来获取所有策略
    strategies = get_all_strategies()
    return render_template('strategy.html', strategies=strategies)

@app.route('/strategy/<strategy_id>')
def strategy(strategy_id):
    # 假设我们有一个函数来获取单个策略的详细信息
    strategy_info = get_strategy_info(strategy_id)
    return render_template('strategy.html', strategy=strategy_info)

def get_all_strategies():
    # 这里应该从数据库或其他数据源获取所有策略
    return [
        {'id': '1', 'name': 'Strategy A', 'description': 'Description of Strategy A'},
        {'id': '2', 'name': 'Strategy B', 'description': 'Description of Strategy B'},
    ]

def get_strategy_info(strategy_id):
    # 假设我们有一个函数来获取单个策略的详细信息
    return {
        'id': strategy_id,
        'name': 'Strategy A',
        'description': 'Description of Strategy A',
        'returns': '10%',
        'details': 'Detailed information about Strategy A',
        'return_curve': [0.05, 0.10, 0.15, 0.20, 0.25],  # Example return curve data
        'holdings': [
            {'symbol': 'AAPL', 'quantity': 100, 'value': 15000},
            {'symbol': 'GOOGL', 'quantity': 50, 'value': 75000}
        ]  # Example holdings data
    }

if __name__ == "__main__":
    app.run()
