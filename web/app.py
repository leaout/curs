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
import logging
import akshare as ak

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

@app.route('/api/signals/debug')
def api_signals_debug():
    """调试：检查信号表状态"""
    try:
        db_manager = get_db_manager()
        
        # 检查表是否存在
        check_table = """
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = 'strategy_signals'
        """
        tables = db_manager.execute_query(check_table)
        
        if not tables:
            return {'error': '表strategy_signals不存在'}
        
        # 检查记录数
        count_query = "SELECT COUNT(*) as cnt FROM strategy_signals"
        count_result = db_manager.execute_query(count_query)
        total_count = count_result[0]['cnt'] if count_result else 0
        
        # 获取最新10条
        recent_query = "SELECT * FROM strategy_signals ORDER BY timestamp DESC LIMIT 10"
        recent = db_manager.execute_query(recent_query)
        
        # 格式化时间
        for r in recent:
            if r.get('timestamp'):
                r['timestamp'] = str(r['timestamp'])
            if r.get('created_at'):
                r['created_at'] = str(r['created_at'])
            if r.get('updated_at'):
                r['updated_at'] = str(r['updated_at'])
        
        return {
            'table_exists': True,
            'total_count': total_count,
            'recent_signals': recent
        }
    except Exception as e:
        return {'error': str(e)}, 500

@app.route('/profit')
def profit():
    """盈利统计页面"""
    return render_template('profit_stats.html')

@app.route('/signal-profit')
def signal_profit():
    """信号盈利分析页面"""
    return render_template('signal_profit.html')

@app.route('/api/signals')
def api_signals():
    """获取策略信号数据"""
    try:
        strategy_name = request.args.get('strategy')
        stock_code = request.args.get('stock')
        signal_type = request.args.get('type')
        status = request.args.get('status')
        limit = int(request.args.get('limit', 1000))  # 默认1000条

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


@app.route('/api/profit/stats')
def api_profit_stats():
    """获取盈利统计数据"""
    try:
        db_manager = get_db_manager()
        
        # 从数据库获取统计摘要
        summary = db_manager.get_profit_stats_summary()
        
        # 如果数据库没有数据，返回提示
        if not summary or summary.get('total_trades', 0) == 0:
            return {
                'total_trades': 0,
                'filled_count': 0,
                'cancelled_count': 0,
                'fill_rate': 0,
                'avg_profit_pct': 0,
                'max_profit_pct': 0,
                'min_profit_pct': 0,
                'win_rate': 0,
                'avg_hold_seconds': 0,
                'message': '暂无盈利数据，请确保策略已运行并成交'
            }
        
        return summary
    except Exception as e:
        return {'error': str(e)}, 500


@app.route('/api/profit/holding-days')
def api_profit_by_holding_days():
    """获取按持有天数统计的盈利数据"""
    try:
        db_manager = get_db_manager()
        
        # 从数据库获取按持有天数统计
        holding_stats = db_manager.get_profit_by_holding_days()
        
        if not holding_stats:
            return {'holding_stats': [], 'message': '暂无持有天数数据'}
        
        return {'holding_stats': holding_stats}
    except Exception as e:
        return {'error': str(e)}, 500


@app.route('/api/profit/max-profit-time')
def api_profit_max_time():
    """获取从信号时间开始往后多少天盈利最多的统计"""
    try:
        db_manager = get_db_manager()
        
        # 从数据库获取记录
        records = db_manager.get_profit_records(status='SOLD', limit=1000)
        
        if not records:
            return {'max_profit_stats': [], 'message': '暂无盈利数据'}
        
        # 统计从信号到最大盈利的时间
        # 由于数据库没有存储profit_points，这个功能暂时返回基本信息
        result = []
        
        # 按买入时间分组统计
        from collections import defaultdict
        time_groups = defaultdict(lambda: {'count': 0, 'profits': []})
        
        for record in records:
            buy_time = record.get('buy_time')
            profit_pct = float(record.get('profit_pct', 0) or 0)
            
            if buy_time:
                # 按买入日期统计
                date_key = buy_time.strftime('%Y-%m-%d') if hasattr(buy_time, 'strftime') else str(buy_time)[:10]
                time_groups[date_key]['count'] += 1
                time_groups[date_key]['profits'].append(profit_pct)
        
        # 汇总统计
        all_profits = []
        for group in time_groups.values():
            all_profits.extend(group['profits'])
        
        if all_profits:
            result.append({
                'time_to_max': '全部',
                'count': len(all_profits),
                'avg_max_profit_pct': sum(all_profits) / len(all_profits),
                'max_profit_pct': max(all_profits),
                'min_profit_pct': min(all_profits),
                'avg_time_seconds': 0
            })
        
        # 获取股票名称
        for record in records[:10]:
            stock_code = record.get('stock_code')
            if stock_code:
                record['stock_name'] = db_manager.get_stock_name(stock_code) or ''
        
        return {
            'max_profit_stats': result,
            'recent_records': records[:20]
        }
    except Exception as e:
        return {'error': str(e)}, 500


@app.route('/api/stock/info/sync', methods=['POST'])
def api_sync_stock_info():
    """同步股票信息"""
    try:
        db_manager = get_db_manager()
        result = db_manager.sync_stock_info_from_qmt()
        return {'status': 'success', 'result': result}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}, 500


@app.route('/api/hotstocks/sync', methods=['POST', 'GET'])
def api_sync_hot_stocks():
    """同步热点股票到数据库（支持GET和POST）"""
    try:
        from curs.collection.hot_stocks import sync_hot_stocks_to_db
        from curs.database import get_db_manager
        
        db_manager = get_db_manager()
        result = sync_hot_stocks_to_db(db_manager, category='hot')
        
        return result
    except Exception as e:
        logger.error(f"同步热点股票失败: {e}")
        return {'status': 'error', 'message': str(e)}, 500


@app.route('/api/hotstocks/clear', methods=['POST', 'GET'])
def api_clear_hot_stocks():
    """清除今天添加的热点股票"""
    try:
        db_manager = get_db_manager()
        
        # 删除今天添加的hot类别股票
        query = """
            DELETE FROM stock_pool 
            WHERE category = 'hot' 
            AND DATE(added_at) = CURRENT_DATE
        """
        result = db_manager.execute_query(query)
        
        # 获取删除数量
        count_query = "SELECT COUNT(*) as cnt FROM stock_pool WHERE category = 'hot'"
        count_result = db_manager.execute_query(count_query)
        remaining = count_result[0]['cnt'] if count_result else 0
        
        return {
            'success': True,
            'message': f'已清除今日热点股票，剩余 {remaining} 只'
        }
    except Exception as e:
        logger.error(f"清除热点股票失败: {e}")
        return {'status': 'error', 'message': str(e)}, 500


@app.route('/api/hotstocks/cache', methods=['GET'])
def api_hot_stocks_cache():
    """获取缓存的热点股票"""
    try:
        from curs.collection.hot_stocks import load_cache
        
        cached = load_cache()
        if cached:
            return {
                'success': True,
                'stocks': cached,
                'count': len(cached)
            }
        else:
            return {'success': False, 'message': '无缓存数据'}
    except Exception as e:
        return {'success': False, 'message': str(e)}, 500


@app.route('/api/signals/profit-analysis')
def api_signals_profit_analysis():
    """
    基于历史信号分析盈利情况
    从信号发出后第2天(T+1)开始统计，考虑A股T+1制度
    """
    try:
        from xtquant import xtdata
        from datetime import timedelta
        from collections import defaultdict
        
        # 获取价格类型参数: high(最高价), close(收盘价), avg(均价)
        price_type = request.args.get('price_type', 'high')
        
        db_manager = get_db_manager()
        
        # 获取已执行的买入信号
        signals = db_manager.get_executed_buy_signals(limit=1000)
        
        if not signals:
            return {'error': '暂无已执行的买入信号'}, 404
        
        # 统计结果
        results = []
        day_stats = defaultdict(lambda: {'count': 0, 'profits': [], 'close_profits': []})
        
        for signal in signals:
            stock_code = signal.get('stock_code')
            buy_price = signal.get('price')
            buy_time = signal.get('timestamp')
            
            if not stock_code or not buy_price or not buy_time:
                continue
            
            # 获取股票名称
            stock_name = signal.get('stock_name') or db_manager.get_stock_name(stock_code) or ''
            
            signal_result = {
                'stock_code': stock_code,
                'stock_name': stock_name,
                'buy_price': float(buy_price),
                'buy_time': buy_time.strftime('%Y-%m-%d %H:%M') if hasattr(buy_time, 'strftime') else str(buy_time),
                'daily_profits': []
            }
            
            try:
                # 下载历史数据
                xtdata.download_history_data(stock_code, period='1d', start_time='', end_time='')
                
                # 获取信号后30天的数据(从T+1开始，即从第2天开始)
                # 如果当天买入，第2天才能卖出
                start_time_str = buy_time.strftime('%Y%m%d') if hasattr(buy_time, 'strftime') else str(buy_time)[:10].replace('-', '')
                
                # 获取更多数据，确保包含T+1之后的数据
                kline_data = xtdata.get_market_data(
                    field_list=['time', 'open', 'high', 'low', 'close', 'volume', 'amount'],
                    stock_list=[stock_code],
                    period='1d',
                    start_time=start_time_str,
                    count=35  # 多获取几天
                )
                
                if kline_data and 'close' in kline_data and stock_code in kline_data['close'].index:
                    close_series = kline_data['close'].loc[stock_code]
                    high_series = kline_data['high'].loc[stock_code]
                    time_series = kline_data['time'].loc[stock_code]
                    
                    # 尝试获取成交量和成交额
                    has_volume = 'volume' in kline_data
                    volume_series = kline_data['volume'].loc[stock_code] if has_volume else None
                    amount_series = kline_data['amount'].loc[stock_code] if 'amount' in kline_data else None
                    
                    max_profit_pct = 0
                    max_profit_day = 0
                    max_profit_close_pct = 0
                    
                    # 从第2天开始统计(T+1)，跳过买入当天
                    for i in range(1, len(close_series)):  # 跳过第0天(买入当天)
                        close_price = close_series.iloc[i]
                        high_price = high_series.iloc[i] if 'high' in kline_data else close_price
                        
                        if pd.notna(close_price) and close_price > 0:
                            # 根据价格类型计算卖出价格
                            if price_type == 'high':
                                sell_price = high_price if pd.notna(high_price) else close_price
                            elif price_type == 'avg':
                                # 均价 = 成交额 / 成交量
                                if has_volume and volume_series is not None:
                                    vol = volume_series.iloc[i]
                                    if pd.notna(vol) and vol > 0 and amount_series is not None:
                                        amt = amount_series.iloc[i]
                                        if pd.notna(amt):
                                            sell_price = amt / vol
                                        else:
                                            sell_price = close_price
                                    else:
                                        sell_price = close_price
                                else:
                                    sell_price = close_price
                            else:  # close
                                sell_price = close_price
                            
                            # 计算基于收盘价的盈利(用于胜率统计)
                            close_profit_pct = (close_price - float(buy_price)) / float(buy_price) * 100
                            
                            # 计算基于选择价格的盈利
                            profit_pct = (sell_price - float(buy_price)) / float(buy_price) * 100
                            
                            holding_days = i + 1  # 持有天数
                            
                            signal_result['daily_profits'].append({
                                'day': holding_days,
                                'price': float(sell_price),
                                'close_price': float(close_price),
                                'profit_pct': float(profit_pct),
                                'close_profit_pct': float(close_profit_pct)
                            })
                            
                            if profit_pct > max_profit_pct:
                                max_profit_pct = profit_pct
                                max_profit_day = holding_days
                            
                            if close_profit_pct > max_profit_close_pct:
                                max_profit_close_pct = close_profit_pct
                    
                    signal_result['max_profit_pct'] = max_profit_pct
                    signal_result['max_profit_day'] = max_profit_day
                    signal_result['max_close_profit_pct'] = max_profit_close_pct
                    
                    # 统计各持有天数的盈利(从T+1开始)
                    for profit_info in signal_result['daily_profits']:
                        day = profit_info['day']
                        profit = profit_info['profit_pct']
                        close_profit = profit_info['close_profit_pct']
                        
                        if day <= 2:
                            day_key = 'T+1(第2天)'
                        elif day <= 3:
                            day_key = 'T+2(第3天)'
                        elif day <= 5:
                            day_key = '3-5天'
                        elif day <= 10:
                            day_key = '6-10天'
                        elif day <= 20:
                            day_key = '11-20天'
                        else:
                            day_key = '20天+'
                        
                        day_stats[day_key]['count'] += 1
                        day_stats[day_key]['profits'].append(profit)
                        day_stats[day_key]['close_profits'].append(close_profit)
                
            except Exception as e:
                logger.warning(f"获取股票{stock_code}价格数据失败: {e}")
                continue
            
            results.append(signal_result)
        
        # 汇总统计
        summary = []
        day_order = ['T+1(第2天)', 'T+2(第3天)', '3-5天', '6-10天', '11-20天', '20天+']
        for day_key in day_order:
            stats = day_stats.get(day_key)
            if stats and stats['count'] > 0:
                profits = stats['profits']
                close_profits = stats['close_profits']
                wins = len([p for p in close_profits if p > 0])
                
                summary.append({
                    'holding_days': day_key,
                    'count': stats['count'],
                    'avg_profit_pct': sum(profits) / len(profits),
                    'max_profit_pct': max(profits),
                    'min_profit_pct': min(profits),
                    'win_rate': wins / len(close_profits) * 100
                })
        
        return {
            'total_signals': len(results),
            'price_type': price_type,
            'note': 'T+1制度：买入当天不能卖出，从第2天开始统计',
            'summary': summary,
            'details': results[:50]
        }
        
    except Exception as e:
        logger.error(f"信号盈利分析失败: {e}")
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
        limit = int(request.args.get('limit', 20))  # 默认每页20条
        page = int(request.args.get('page', 1))     # 默认第1页
        offset = (page - 1) * limit

        db_manager = get_db_manager()
        stocks = db_manager.get_stock_pool(category=category, limit=limit, offset=offset)

        # 获取总数用于分页
        total_query = "SELECT COUNT(*) as total FROM stock_pool WHERE is_active = TRUE"
        if category:
            total_query += f" AND category = '{category}'"
        total_result = db_manager.execute_query(total_query)
        total = total_result[0]['total'] if total_result else 0

        # 格式化时间戳
        for stock in stocks:
            if 'added_at' in stock and stock['added_at']:
                stock['added_at'] = stock['added_at'].strftime('%Y-%m-%d %H:%M:%S')
            if 'updated_at' in stock and stock['updated_at']:
                stock['updated_at'] = stock['updated_at'].strftime('%Y-%m-%d %H:%M:%S')

        return {
            'stocks': stocks,
            'total': total,
            'page': page,
            'limit': limit,
            'total_pages': (total + limit - 1) // limit  # 向上取整
        }
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

# ===== 持仓管理路由 =====

@app.route('/positions')
def positions():
    """持仓管理页面"""
    return render_template('positions.html')

@app.route('/api/positions')
def api_positions():
    """获取持仓信息"""
    try:
        # 从策略服务获取持仓数据
        strategy_service_url = 'http://localhost:5001/api/positions'
        response = requests.get(strategy_service_url, timeout=10)

        if response.status_code == 200:
            return response.json()
        else:
            return {'error': f'策略服务返回错误: {response.status_code}'}, response.status_code

    except requests.exceptions.RequestException as e:
        return {'error': f'无法连接到策略服务: {str(e)}'}, 500
    except Exception as e:
        return {'error': str(e)}, 500

@app.route('/api/liquidate', methods=['POST'])
def api_liquidate():
    """一键清仓"""
    try:
        # 向策略服务发送清仓请求
        strategy_service_url = 'http://localhost:5001/api/liquidate'
        response = requests.post(strategy_service_url, timeout=10)

        if response.status_code == 200:
            return response.json()
        else:
            return {'success': False, 'message': f'策略服务返回错误: {response.status_code}'}, response.status_code

    except requests.exceptions.RequestException as e:
        return {'success': False, 'message': f'无法连接到策略服务: {str(e)}'}, 500
    except Exception as e:
        return {'success': False, 'message': str(e)}, 500

@app.route('/api/liquidate/<stock_code>', methods=['POST'])
def api_liquidate_stock(stock_code):
    """清仓单个股票"""
    try:
        # 向策略服务发送清仓请求
        strategy_service_url = f'http://localhost:5001/api/liquidate/{stock_code}'
        response = requests.post(strategy_service_url, timeout=10)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 400:
            return {'success': False, 'message': '无效的股票代码'}, 400
        else:
            return {'success': False, 'message': f'策略服务返回错误: {response.status_code}'}, response.status_code

    except requests.exceptions.RequestException as e:
        return {'success': False, 'message': f'无法连接到策略服务: {str(e)}'}, 500
    except Exception as e:
        return {'success': False, 'message': str(e)}, 500

# ===== 股票详情路由 =====

@app.route('/api/stock/<stock_code>/kline')
def api_stock_kline(stock_code):
    """获取股票K线数据"""
    try:
        if not is_valid_stock_code(stock_code):
            return {'error': '无效的股票代码格式'}, 400

        # 从策略服务请求K线数据
        strategy_service_url = 'http://localhost:5001/api/stock/{}/kline'.format(stock_code)
        response = requests.get(strategy_service_url, timeout=10)

        if response.status_code == 200:
            return response.json()
        else:
            return {'error': f'策略服务返回错误: {response.status_code}'}, response.status_code

    except requests.exceptions.RequestException as e:
        return {'error': f'无法连接到策略服务: {str(e)}'}, 500
    except Exception as e:
        return {'error': str(e)}, 500

@app.route('/api/stock/<stock_code>/quote')
def api_stock_quote(stock_code):
    """获取股票当日行情"""
    try:
        if not is_valid_stock_code(stock_code):
            return {'error': '无效的股票代码格式'}, 400

        # 从策略服务请求行情数据
        strategy_service_url = 'http://localhost:5001/api/stock/{}/quote'.format(stock_code)
        response = requests.get(strategy_service_url, timeout=10)

        if response.status_code == 200:
            return response.json()
        else:
            return {'error': f'策略服务返回错误: {response.status_code}'}, response.status_code

    except requests.exceptions.RequestException as e:
        return {'error': f'无法连接到策略服务: {str(e)}'}, 500
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
                    <h3>💼 持仓管理</h3>
                    <p>查看QMT持仓信息，支持一键清仓和单股票清仓操作</p>
                    <a href="/positions" class="nav-button">进入持仓管理</a>
                </div>

                <div class="nav-card">
                    <h3>⚙️ 系统设置</h3>
                    <p>配置系统参数，管理数据库连接和交易账户</p>
                    <a href="#" class="nav-button" onclick="alert('功能开发中')">进入系统设置</a>
                </div>

                <div class="nav-card">
                    <h3>⏰ 定时任务</h3>
                    <p>配置和管理定时任务，查看任务执行日志</p>
                    <a href="/tasks" class="nav-button">进入定时任务</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    '''

# ===== 定时任务管理路由 =====

@app.route('/tasks')
def tasks_page():
    """定时任务管理页面"""
    return render_template('tasks.html')

@app.route('/api/tasks', methods=['GET'])
def api_get_tasks():
    """获取所有定时任务"""
    try:
        db_manager = get_db_manager()
        tasks = db_manager.get_all_scheduled_tasks()
        
        for task in tasks:
            if task.get('last_run_at'):
                task['last_run_at'] = task['last_run_at'].strftime('%Y-%m-%d %H:%M:%S')
            if task.get('next_run_at'):
                task['next_run_at'] = task['next_run_at'].strftime('%Y-%m-%d %H:%M:%S')
            if task.get('created_at'):
                task['created_at'] = task['created_at'].strftime('%Y-%m-%d %H:%M:%S')
            if task.get('updated_at'):
                task['updated_at'] = task['updated_at'].strftime('%Y-%m-%d %H:%M:%S')
            if task.get('config') and isinstance(task['config'], str):
                task['config'] = json.loads(task['config'])
        
        return {'tasks': tasks, 'total': len(tasks)}
    except Exception as e:
        logger.error(f"获取定时任务失败: {e}")
        return {'error': str(e)}, 500

@app.route('/api/tasks', methods=['POST'])
def api_create_task():
    """创建定时任务"""
    try:
        data = request.get_json()
        
        name = data.get('name', '').strip()
        task_type = data.get('task_type', '').strip()
        cron_expression = data.get('cron_expression', '').strip() or None
        interval_seconds = data.get('interval_seconds')
        is_enabled = data.get('is_enabled', True)
        config = data.get('config', {})
        
        if not name or not task_type:
            return {'success': False, 'message': '任务名称和类型不能为空'}, 400
        
        if not cron_expression and not interval_seconds:
            return {'success': False, 'message': '必须指定cron表达式或间隔秒数'}, 400
        
        db_manager = get_db_manager()
        task_id = db_manager.save_scheduled_task(
            name=name,
            task_type=task_type,
            cron_expression=cron_expression,
            interval_seconds=interval_seconds,
            is_enabled=is_enabled,
            config=config
        )
        
        if task_id:
            return {'success': True, 'message': f'任务 {name} 已创建', 'task_id': task_id}
        else:
            return {'success': False, 'message': '创建任务失败'}, 500
    except Exception as e:
        logger.error(f"创建定时任务失败: {e}")
        return {'success': False, 'message': str(e)}, 500

@app.route('/api/tasks/<int:task_id>', methods=['PUT'])
def api_update_task(task_id):
    """更新定时任务"""
    try:
        data = request.get_json()
        
        update_fields = {}
        if 'name' in data:
            update_fields['name'] = data['name'].strip()
        if 'task_type' in data:
            update_fields['task_type'] = data['task_type'].strip()
        if 'cron_expression' in data:
            update_fields['cron_expression'] = data['cron_expression'].strip() or None
        if 'interval_seconds' in data:
            update_fields['interval_seconds'] = data['interval_seconds']
        if 'is_enabled' in data:
            update_fields['is_enabled'] = data['is_enabled']
        if 'config' in data:
            update_fields['config'] = data['config']
        
        if not update_fields:
            return {'success': False, 'message': '没有需要更新的字段'}, 400
        
        db_manager = get_db_manager()
        if db_manager.update_scheduled_task(task_id, **update_fields):
            return {'success': True, 'message': '任务已更新'}
        else:
            return {'success': False, 'message': '更新任务失败'}, 500
    except Exception as e:
        logger.error(f"更新定时任务失败: {e}")
        return {'success': False, 'message': str(e)}, 500

@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def api_delete_task(task_id):
    """删除定时任务"""
    try:
        db_manager = get_db_manager()
        if db_manager.delete_scheduled_task(task_id):
            return {'success': True, 'message': '任务已删除'}
        else:
            return {'success': False, 'message': '删除任务失败'}, 500
    except Exception as e:
        logger.error(f"删除定时任务失败: {e}")
        return {'success': False, 'message': str(e)}, 500

@app.route('/api/tasks/<int:task_id>/toggle', methods=['POST'])
def api_toggle_task(task_id):
    """启用/禁用定时任务"""
    try:
        data = request.get_json()
        enabled = data.get('enabled', True)
        
        db_manager = get_db_manager()
        if db_manager.enable_scheduled_task(task_id, enabled):
            status = '启用' if enabled else '禁用'
            return {'success': True, 'message': f'任务已{status}'}
        else:
            return {'success': False, 'message': '操作失败'}, 500
    except Exception as e:
        logger.error(f"切换任务状态失败: {e}")
        return {'success': False, 'message': str(e)}, 500

@app.route('/api/tasks/<int:task_id>/logs', methods=['GET'])
def api_task_logs(task_id):
    """获取任务执行日志"""
    try:
        limit = int(request.args.get('limit', 100))
        
        db_manager = get_db_manager()
        logs = db_manager.get_task_logs(task_id, limit)
        
        for log in logs:
            if log.get('started_at'):
                log['started_at'] = log['started_at'].strftime('%Y-%m-%d %H:%M:%S')
            if log.get('finished_at'):
                log['finished_at'] = log['finished_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        stats = db_manager.get_task_stats(task_id)
        
        return {'logs': logs, 'stats': stats}
    except Exception as e:
        logger.error(f"获取任务日志失败: {e}")
        return {'error': str(e)}, 500

@app.route('/api/tasks/types', methods=['GET'])
def api_task_types():
    """获取支持的任务类型"""
    return {
        'types': [
            {'id': 'sync_hot_stocks', 'name': '同步热点股票', 'description': '从网络获取热点股票并同步到数据库'},
            {'id': 'sync_stock_info', 'name': '同步股票信息', 'description': '从QMT同步股票基本信息'},
            {'id': 'profit_analysis', 'name': '盈利分析', 'description': '分析策略信号的盈利情况'},
            {'id': 'clear_hot_stocks', 'name': '清除热点股票', 'description': '清除当天添加的热点股票'},
            {'id': 'custom', 'name': '自定义任务', 'description': '执行自定义Python代码'},
        ]
    }

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
