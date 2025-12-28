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
import akshare as ak
from xtquant import xtdata
# 将项目根目录添加到PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# from curs.strategy.strategy_loader import StrategyManager
from curs.database import get_db_manager
from curs.utils import is_valid_stock_code, format_stock_code

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

@app.route('/signals')
def signals():
    """信号查询页面"""
    return render_template('signals.html')

@app.route('/api/signals')
def api_signals():
    """获取策略信号数据"""
    try:
        strategy_name = request.args.get('strategy')
        stock_code = request.args.get('stock')
        signal_type = request.args.get('type')
        status = request.args.get('status')
        limit = int(request.args.get('limit', 100))

        db_manager = get_db_manager()
        signals = db_manager.get_strategy_signals(
            strategy_name=strategy_name if strategy_name else None,
            stock_code=stock_code if stock_code else None,
            signal_type=signal_type if signal_type else None,
            status=status if status else None,
            limit=limit
        )

        # 格式化时间戳
        for signal in signals:
            if 'timestamp' in signal and signal['timestamp']:
                signal['timestamp'] = signal['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
            if 'created_at' in signal and signal['created_at']:
                signal['created_at'] = signal['created_at'].strftime('%Y-%m-%d %H:%M:%S')
            if 'updated_at' in signal and signal['updated_at']:
                signal['updated_at'] = signal['updated_at'].strftime('%Y-%m-%d %H:%M:%S')

        return {'signals': signals, 'total': len(signals)}
    except Exception as e:
        return {'error': str(e)}, 500

@app.route('/api/signals/stats')
def api_signals_stats():
    """获取信号统计数据"""
    try:
        db_manager = get_db_manager()

        # 获取所有信号
        all_signals = db_manager.get_strategy_signals(limit=10000)

        # 按策略分组统计
        strategy_stats = {}
        status_stats = {'PENDING': 0, 'EXECUTED': 0, 'CANCELLED': 0}
        type_stats = {'BUY': 0, 'SELL': 0}

        for signal in all_signals:
            strategy = signal.get('strategy_name', 'unknown')
            status = signal.get('status', 'unknown')
            signal_type = signal.get('signal_type', 'unknown')

            if strategy not in strategy_stats:
                strategy_stats[strategy] = 0
            strategy_stats[strategy] += 1

            if status in status_stats:
                status_stats[status] += 1

            if signal_type in type_stats:
                type_stats[signal_type] += 1

        return {
            'strategy_stats': strategy_stats,
            'status_stats': status_stats,
            'type_stats': type_stats,
            'total_signals': len(all_signals)
        }
    except Exception as e:
        return {'error': str(e)}, 500

# ===== 股票池管理路由 =====

@app.route('/stockpool')
def stockpool():
    """股票池管理页面"""
    return render_template('stockpool.html')

@app.route('/api/stockpool')
def api_stockpool():
    """获取股票池数据"""
    try:
        category = request.args.get('category')
        limit = int(request.args.get('limit', 1000))

        db_manager = get_db_manager()
        stocks = db_manager.get_stock_pool(category=category, limit=limit)

        # 格式化时间戳
        for stock in stocks:
            if 'added_at' in stock and stock['added_at']:
                stock['added_at'] = stock['added_at'].strftime('%Y-%m-%d %H:%M:%S')
            if 'updated_at' in stock and stock['updated_at']:
                stock['updated_at'] = stock['updated_at'].strftime('%Y-%m-%d %H:%M:%S')

        return {'stocks': stocks, 'total': len(stocks)}
    except Exception as e:
        return {'error': str(e)}, 500

@app.route('/api/stockpool/stats')
def api_stockpool_stats():
    """获取股票池统计数据"""
    try:
        db_manager = get_db_manager()
        stats = db_manager.get_stock_pool_stats()
        return stats
    except Exception as e:
        return {'error': str(e)}, 500

@app.route('/api/stockpool/add', methods=['POST'])
def api_add_stock():
    """添加股票到股票池"""
    try:
        data = request.get_json()
        stock_code = data.get('stock_code', '').strip()
        stock_name = data.get('stock_name', '').strip() or None
        category = data.get('category', 'default')
        notes = data.get('notes', '').strip() or None

        if not stock_code:
            return {'success': False, 'message': '股票代码不能为空'}, 400

        # 验证股票代码格式
        if not is_valid_stock_code(stock_code):
            return {'success': False, 'message': '股票代码格式无效，请使用格式如：601059.SH 或 002549.SZ'}, 400

        # 格式化股票代码（确保后缀大写）
        stock_code = format_stock_code(stock_code)

        db_manager = get_db_manager()
        if db_manager.add_stock_to_pool(stock_code, stock_name, category, 'web', notes):
            return {'success': True, 'message': f'股票 {stock_code} 已添加到股票池'}
        else:
            return {'success': False, 'message': '添加股票失败'}, 500
    except Exception as e:
        return {'success': False, 'message': str(e)}, 500

@app.route('/api/stockpool/batch_add', methods=['POST'])
def api_batch_add_stocks():
    """批量添加股票到股票池"""
    try:
        data = request.get_json()
        stocks_text = data.get('stocks', '').strip()
        category = data.get('category', 'default')

        if not stocks_text:
            return {'success': False, 'message': '股票列表不能为空'}, 400

        # 解析股票列表
        stocks = []
        invalid_codes = []
        for line in stocks_text.split('\n'):
            line = line.strip()
            if line:
                # 支持多种格式：000001 或 000001 平安银行 或 000001,平安银行
                if ',' in line:
                    parts = line.split(',', 1)
                    code = parts[0].strip()
                    name = parts[1].strip() if len(parts) > 1 else ''
                elif ' ' in line:
                    parts = line.split(' ', 1)
                    code = parts[0].strip()
                    name = parts[1].strip() if len(parts) > 1 else ''
                else:
                    code = line
                    name = ''

                # 验证股票代码格式
                if is_valid_stock_code(code):
                    # 格式化股票代码
                    code = format_stock_code(code)
                    stocks.append({
                        'code': code,
                        'name': name
                    })
                else:
                    invalid_codes.append(code)

        if invalid_codes:
            return {'success': False, 'message': f'以下股票代码格式无效：{", ".join(invalid_codes)}。请使用格式如：601059.SH 或 002549.SZ'}, 400

        if not stocks:
            return {'success': False, 'message': '没有找到有效的股票代码'}, 400

        db_manager = get_db_manager()
        result = db_manager.batch_add_stocks_to_pool(stocks, category, 'web')

        message = f'成功添加 {result["success_count"]} 只股票'
        if result['failed_count'] > 0:
            message += f'，失败 {result["failed_count"]} 只'

        return {
            'success': True,
            'message': message,
            'result': result
        }
    except Exception as e:
        return {'success': False, 'message': str(e)}, 500

@app.route('/api/stockpool/remove/<stock_code>', methods=['DELETE'])
def api_remove_stock(stock_code):
    """从股票池中移除股票"""
    try:
        db_manager = get_db_manager()
        if db_manager.remove_stock_from_pool(stock_code):
            return {'success': True, 'message': f'股票 {stock_code} 已从股票池中移除'}
        else:
            return {'success': False, 'message': '移除股票失败'}, 500
    except Exception as e:
        return {'success': False, 'message': str(e)}, 500

@app.route('/api/stockpool/batch_remove', methods=['POST'])
def api_batch_remove_stocks():
    """批量从股票池中移除股票"""
    try:
        data = request.get_json()
        stock_codes = data.get('stock_codes', [])

        if not stock_codes:
            return {'success': False, 'message': '股票代码列表不能为空'}, 400

        db_manager = get_db_manager()
        result = db_manager.batch_remove_stocks_from_pool(stock_codes)

        message = f'成功移除 {result["success_count"]} 只股票'
        if result['failed_count'] > 0:
            message += f'，失败 {result["failed_count"]} 只'

        return {
            'success': True,
            'message': message,
            'result': result
        }
    except Exception as e:
        return {'success': False, 'message': str(e)}, 500

@app.route('/api/stockpool/update_category', methods=['POST'])
def api_update_stock_category():
    """更新股票分类"""
    try:
        data = request.get_json()
        stock_code = data.get('stock_code', '').strip()
        category = data.get('category', 'default')

        if not stock_code:
            return {'success': False, 'message': '股票代码不能为空'}, 400

        db_manager = get_db_manager()
        if db_manager.update_stock_pool_category(stock_code, category):
            return {'success': True, 'message': f'股票 {stock_code} 分类已更新为 {category}'}
        else:
            return {'success': False, 'message': '更新分类失败'}, 500
    except Exception as e:
        return {'success': False, 'message': str(e)}, 500

# ===== 股票详情路由 =====

@app.route('/api/stock/<stock_code>/kline')
def api_stock_kline(stock_code):
    """获取股票K线数据"""
    try:
        if not is_valid_stock_code(stock_code):
            return {'error': '无效的股票代码格式'}, 400

        # 首先下载历史数据（如果需要）
        try:
            # 下载最近60天的日K线数据
            xtdata.download_history_data(stock_code, period='1d', start_time='', end_time='')
        except Exception as download_error:
            print(f"下载历史数据失败: {download_error}")
            # 如果下载失败，继续尝试获取现有数据

        # 使用QMT获取日K线数据
        kline_data = xtdata.get_market_data(
            field_list=['time', 'open', 'high', 'low', 'close', 'volume', 'amount'],
            stock_list=[stock_code],
            period='1d',  # 日K线
            count=60  # 最近60天
        )

        if not kline_data or 'time' not in kline_data:
            return {'error': '未找到股票数据'}, 404

        # 获取各个字段的DataFrame
        time_df = kline_data['time']
        open_df = kline_data['open']
        high_df = kline_data['high']
        low_df = kline_data['low']
        close_df = kline_data['close']
        volume_df = kline_data['volume']

        # 检查是否有数据
        if stock_code not in time_df.index:
            return {'error': '未找到股票数据'}, 404

        # 提取该股票的数据
        times = time_df.loc[stock_code]
        opens = open_df.loc[stock_code]
        highs = high_df.loc[stock_code]
        lows = low_df.loc[stock_code]
        closes = close_df.loc[stock_code]
        volumes = volume_df.loc[stock_code]

        # 格式化数据为ECharts K线图格式 [开盘, 收盘, 最低, 最高]
        echarts_kline = []
        dates = []
        volume_list = []

        # 按时间顺序整理数据
        for i in range(len(times)):
            if pd.notna(times.iloc[i]) and pd.notna(opens.iloc[i]):
                try:
                    # QMT时间戳可能是毫秒格式，尝试转换
                    timestamp = times.iloc[i]
                    if timestamp > 1e10:  # 如果是毫秒时间戳
                        timestamp = timestamp / 1000

                    # 时间戳转换为日期字符串
                    date = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
                    dates.append(date)
                    echarts_kline.append([
                        float(opens.iloc[i]),  # open
                        float(closes.iloc[i]), # close
                        float(lows.iloc[i]),   # low
                        float(highs.iloc[i])   # high
                    ])
                    volume_list.append(float(volumes.iloc[i]))
                except (ValueError, OSError) as e:
                    # 如果时间戳转换失败，跳过这条数据
                    print(f"跳过无效时间戳: {times.iloc[i]}, 错误: {e}")
                    continue

        if not dates:
            return {'error': '未找到有效的股票数据'}, 404

        return {
            'stock_code': stock_code,
            'dates': dates,
            'kline_data': echarts_kline,
            'volumes': volume_list
        }
    except Exception as e:
        return {'error': str(e)}, 500

@app.route('/api/stock/<stock_code>/quote')
def api_stock_quote(stock_code):
    """获取股票当日行情"""
    try:
        if not is_valid_stock_code(stock_code):
            return {'error': '无效的股票代码格式'}, 400

        # 尝试使用QMT获取实时行情数据
        try:
            # 使用get_market_data_ex获取最新分笔数据
            quote_data = xtdata.get_market_data_ex(
                field_list=['time', 'open', 'high', 'low', 'close', 'volume', 'amount'],
                stock_list=[stock_code],
                period='tick',  # 分笔数据
                count=1  # 最新一条
            )

            if quote_data and 'close' in quote_data and stock_code in quote_data['close'].index:
                close_df = quote_data['close']
                volume_df = quote_data['volume']
                amount_df = quote_data['amount']
                high_df = quote_data['high']
                low_df = quote_data['low']
                open_df = quote_data['open']

                last_price = float(close_df.loc[stock_code].iloc[-1]) if not close_df.loc[stock_code].empty else 0
                volume = int(volume_df.loc[stock_code].iloc[-1]) if not volume_df.loc[stock_code].empty else 0
                amount = float(amount_df.loc[stock_code].iloc[-1]) if not amount_df.loc[stock_code].empty else 0
                high = float(high_df.loc[stock_code].iloc[-1]) if not high_df.loc[stock_code].empty else 0
                low = float(low_df.loc[stock_code].iloc[-1]) if not low_df.loc[stock_code].empty else 0
                open_price = float(open_df.loc[stock_code].iloc[-1]) if not open_df.loc[stock_code].empty else 0
            else:
                # 如果QMT获取失败，回退到akshare
                raise Exception("QMT data not available")

        except Exception as qmt_error:
            print(f"QMT获取行情失败: {qmt_error}，尝试使用akshare")

            # 使用akshare作为备用数据源
            code = stock_code.split('.')[0]
            market = stock_code.split('.')[1].lower()

            df = ak.stock_zh_a_spot_em()
            stock_data = df[df['代码'] == code]

            if stock_data.empty:
                return {'error': '未找到股票行情数据'}, 404

            data = stock_data.iloc[0]

            return {
                'stock_code': stock_code,
                'name': data['名称'],
                'price': float(data['最新价']),
                'change': float(data['涨跌额']),
                'change_percent': float(data['涨跌幅']),
                'volume': int(data['成交量']),
                'amount': float(data['成交额']),
                'high': float(data['最高']),
                'low': float(data['最低']),
                'open': float(data['今开']),
                'close': float(data['昨收']),
                'turnover': float(data['换手率']),
                'pe': float(data['市盈率-动态']) if pd.notna(data['市盈率-动态']) else None,
                'market_cap': float(data['总市值']) if pd.notna(data['总市值']) else None,
                'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

        # 获取股票基本信息
        instrument_detail = xtdata.get_instrument_detail(stock_code, False)
        stock_name = instrument_detail.get('InstrumentName', '') if instrument_detail else ''

        # 获取昨收价用于计算涨跌幅
        try:
            # 获取前一天的数据来获取昨收价
            pre_data = xtdata.get_market_data(
                field_list=['close'],
                stock_list=[stock_code],
                period='1d',
                count=2  # 获取最近2天的数据
            )
            if pre_data and 'close' in pre_data and stock_code in pre_data['close'].index:
                close_df = pre_data['close']
                pre_close = float(close_df.loc[stock_code].iloc[-2]) if len(close_df.loc[stock_code]) >= 2 else last_price
            else:
                pre_close = last_price
        except:
            pre_close = last_price

        # 计算涨跌幅和涨跌额
        change = last_price - pre_close
        change_percent = (change / pre_close * 100) if pre_close > 0 else 0

        return {
            'stock_code': stock_code,
            'name': stock_name,
            'price': float(last_price),
            'change': float(change),
            'change_percent': float(change_percent),
            'volume': int(volume),
            'amount': float(amount),
            'high': float(high),
            'low': float(low),
            'open': float(open_price),
            'close': float(pre_close),
            'turnover': 0.0,  # QMT不直接提供换手率
            'pe': None,  # QMT不直接提供市盈率
            'market_cap': None,  # QMT不直接提供市值
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    except Exception as e:
        return {'error': str(e)}, 500

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

    # 获取信号统计
    db_manager = get_db_manager()
    try:
        signals_stats = db_manager.get_strategy_signals(strategy_name=strategy_id, limit=1000)
        today_signals = sum(1 for signal in signals_stats
                           if signal.get('timestamp', '').startswith(datetime.now().strftime('%Y-%m-%d')))
        pending_signals = sum(1 for signal in signals_stats if signal.get('status') == 'PENDING')
        executed_signals = sum(1 for signal in signals_stats if signal.get('status') == 'EXECUTED')
    except Exception as e:
        today_signals = 0
        pending_signals = 0
        executed_signals = 0

    # 计算收益率（简单计算）
    total_return = 0
    if trades:
        # 假设每笔交易的收益为固定比例，这里简化为成功率作为收益率
        total_return = success_rate

    return {
        'id': strategy_id,
        'name': strategy_id.replace('_', ' ').title(),
        'description': f'{strategy_id} 量化交易策略',
        'returns': f'{total_return:.2f}%',
        'details': f'Total trades: {total_trades}, Success rate: {success_rate:.2f}%',
        'return_curve': [trade.get('profit', success_rate/10) for trade in trades[-30:]],  # 最近30笔交易收益
        'holdings': [],  # 当前持仓
        'positions': trades,  # 历史交易记录
        'signal_stats': {
            'today_signals': today_signals,
            'pending_signals': pending_signals,
            'executed_signals': executed_signals,
            'total_signals': len(signals_stats)
        }
    }

@app.route('/')
def index():
    """主页"""
    return '''
    <html>
    <head>
        <title>量化交易系统</title>
        <style>
            body { font-family: Arial, sans-serif; background: #f2f2f2; margin: 0; padding: 20px; }
            .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
            h1 { color: #2c3e50; text-align: center; }
            .nav-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-top: 30px; }
            .nav-card { background: #f8f9fa; padding: 20px; border-radius: 6px; text-align: center; border: 1px solid #dee2e6; transition: transform 0.2s; }
            .nav-card:hover { transform: translateY(-2px); box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
            .nav-card h3 { margin: 0 0 10px 0; color: #495057; }
            .nav-card p { margin: 10px 0; color: #6c757d; }
            .nav-button { display: inline-block; background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; margin-top: 10px; }
            .nav-button:hover { background: #0056b3; color: white; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>量化交易系统</h1>
            <p style="text-align: center; color: #6c757d;">选择您要访问的功能模块</p>

            <div class="nav-grid">
                <div class="nav-card">
                    <h3>📊 策略管理</h3>
                    <p>查看和管理交易策略，监控策略运行状态和性能指标</p>
                    <a href="/strategies" class="nav-button">进入策略管理</a>
                </div>

                <div class="nav-card">
                    <h3>📈 信号查询</h3>
                    <p>实时查看策略生成的买卖信号，支持多维度筛选和统计</p>
                    <a href="/signals" class="nav-button">进入信号查询</a>
                </div>

                <div class="nav-card">
                    <h3>🏊 股票池管理</h3>
                    <p>管理股票池，支持批量添加删除股票，按分类管理</p>
                    <a href="/stockpool" class="nav-button">进入股票池</a>
                </div>

                <div class="nav-card">
                    <h3>⚙️ 系统设置</h3>
                    <p>配置系统参数，管理数据库连接和交易账户</p>
                    <a href="#" class="nav-button" onclick="alert('功能开发中')">进入系统设置</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    '''

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
