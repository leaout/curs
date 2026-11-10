# coding: utf-8
import os
import csv
import json
import time
import math
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, redirect, request, render_template, url_for
import pandas as pd
import requests
import sys
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 将项目根目录添加到PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# from curs.strategy.strategy_loader import StrategyManager
from curs.database import get_db_manager
from curs.utils import is_valid_stock_code, format_stock_code
from curs.utils.task_callbacks import (
    task_sync_hot_stocks,
    task_collect_hot_stocks,
    task_sync_stock_info,
    task_profit_analysis,
    task_clear_hot_stocks,
    execute_dynamic_task,
)

TASK_CALLBACKS = {
    'sync_hot_stocks': task_sync_hot_stocks,
    'collect_hot_stocks': task_collect_hot_stocks,
    'sync_stock_info': task_sync_stock_info,
    'profit_analysis': task_profit_analysis,
    'clear_hot_stocks': task_clear_hot_stocks,
    'custom_script': execute_dynamic_task,
    'custom': execute_dynamic_task,
}

app = Flask(__name__)


@app.route('/finance-board')
def finance_board_page():
    return render_template('finance_board.html')


@app.route('/api/finance-board')
def api_finance_board():
    from curs.finance_board import board_report
    report_day = request.args.get('date')
    if report_day:
        try:
            if datetime.strptime(report_day, '%Y-%m-%d').date().isoformat() != report_day:
                raise ValueError
        except ValueError:
            return {'error': '日期格式应为 YYYY-MM-DD'}, 400
    return board_report(force=request.args.get('refresh') == '1', report_day=report_day)


@app.route('/api/market-report')
def api_market_report():
    from curs.stock_intel import market_report
    day = request.args.get('date', '')
    try:
        if datetime.strptime(day, '%Y-%m-%d').date().isoformat() != day:
            raise ValueError
    except ValueError:
        return {'error': '日期格式应为 YYYY-MM-DD'}, 400
    return {'report': market_report(day)}


@app.route('/api/finance-board/desktop-bridge', methods=['GET', 'POST'])
def api_finance_board_bridge():
    from urllib.parse import urlsplit
    from curs import workbuddy_desktop

    origin = request.host_url.rstrip('/')
    if (request.remote_addr not in ('127.0.0.1', '::1')
            or urlsplit(origin).hostname not in ('localhost', '127.0.0.1', '::1')):
        return {'error': '请从本机研究台调用 Desktop Bridge'}, 403
    if request.method == 'GET':
        return workbuddy_desktop.status(check=request.args.get('check') == '1')
    if request.headers.get('Origin') != origin:
        return {'error': '请求来源不匹配'}, 403
    body = request.get_json(silent=True)
    try:
        body = body if isinstance(body, dict) else {}
        workbuddy_desktop.start(body.get('stock_code'), all_stocks=body.get('all_stocks') is True)
    except ValueError as exc:
        return {'error': str(exc)}, 400
    except (RuntimeError, OSError) as exc:
        return {'error': str(exc)}, 409
    return workbuddy_desktop.status(), 202


@app.after_request
def add_security_display_names(response):
    if request.path.startswith('/api/') and response.is_json and response.status_code == 200:
        from curs.stock_names import enrich
        try:
            payload = enrich(response.get_json())
            response.set_data(app.json.dumps(payload))
        except Exception:
            logger.exception('Security name enrichment failed')
    return response


@app.route('/market-sentiment')
def market_sentiment_page():
    return render_template('market_sentiment.html')


@app.route('/api/market-sentiment')
def api_market_sentiment():
    from curs.market_sentiment import report
    from curs.core.engine import Engine
    result = report()
    from curs.relay import report as relay_report
    result['relay'] = relay_report()
    try:
        result['collector'] = Engine.get_instance().get_sentiment_status()
    except RuntimeError:
        result['collector'] = {'running': False, 'reason': '引擎未启动'}
    return result


@app.route('/signal-review')
def signal_review():
    return redirect(url_for('signals', view='review'))


@app.route('/api/signal-review')
def api_signal_review():
    from curs.signal_observer import report
    from curs.first_board import candidates
    result = report()
    result['candidates'] = candidates()
    return result


@app.route('/api/health')
def api_health():
    from curs.core.engine import Engine
    from curs.strategy_manager import StrategyManager
    try:
        engine = Engine.get_instance()
        return {'service': 'curs', 'running': engine._running,
                'quotes': engine.get_quote_stats(),
                'strategies': StrategyManager.get_instance().list_strategies(),
                'mode': 'signal_only'}
    except RuntimeError:
        return {'service': 'curs', 'running': False, 'mode': 'signal_only'}, 503

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
    return redirect(url_for('manage', section='strategies'))

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
    return redirect(url_for('manage', section='strategies', strategy=strategy_id))

@app.route('/strategy/<strategy_id>/start', methods=['POST'])
def start_strategy(strategy_id):
    """启动策略实盘"""
    try:
        from curs.strategy_manager import StrategyManager
        result = StrategyManager.get_instance().enable_strategy(strategy_id)
        if result:
            return {'status': 'success', 'message': '策略已启动', 'enabled': True}
        return {'status': 'error', 'message': f'策略 {strategy_id} 未加载'}, 404
    except RuntimeError:
        response = requests.post(
            f'http://localhost:5001/api/strategy/{strategy_id}/toggle',
            json={'enabled': True},
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
        return {'status': 'error', 'message': '策略启动失败'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

@app.route('/strategy/<strategy_id>/stop', methods=['POST'])
def stop_strategy(strategy_id):
    """停止策略实盘（仅信号模式）"""
    try:
        from curs.strategy_manager import StrategyManager
        result = StrategyManager.get_instance().disable_strategy(strategy_id)
        if result:
            return {'status': 'success', 'message': '已切换为信号模式', 'enabled': False}
        return {'status': 'error', 'message': f'策略 {strategy_id} 未加载'}, 404
    except RuntimeError:
        response = requests.post(
            f'http://localhost:5001/api/strategy/{strategy_id}/toggle',
            json={'enabled': False},
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
        return {'status': 'error', 'message': '策略停止失败'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

@app.route('/api/strategy/<strategy_id>/toggle', methods=['POST'])
def api_strategy_toggle(strategy_id):
    """启用/禁用策略实盘交易"""
    try:
        data = request.get_json()
        enabled = data.get('enabled', True)
        from curs.strategy_manager import StrategyManager
        if enabled:
            ok = StrategyManager.get_instance().enable_strategy(strategy_id)
        else:
            ok = StrategyManager.get_instance().disable_strategy(strategy_id)
        if ok:
            return {'status': 'success', 'enabled': enabled}
        return {'status': 'error', 'message': f'策略 {strategy_id} 未加载'}, 404
    except RuntimeError:
        # 单例不存在 → 降级为 HTTP proxy（兼容 curs_main.py 模式）
        try:
            data = request.get_json()
            enabled = data.get('enabled', True)
            response = requests.post(
                f'http://localhost:5001/api/strategy/{strategy_id}/toggle',
                json={'enabled': enabled},
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
            return {'status': 'error', 'message': '切换失败'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}, 500
    except Exception as e:
        return {'status': 'error', 'message': str(e)}, 500

@app.route('/signals')
def signals():
    """信号查询页面"""
    filters = {key: request.args[key] for key in ('date', 'strategy', 'stock', 'type', 'status', 'limit')
               if key in request.args}
    if request.args.get('view') == 'review':
        return render_template('signal_review.html', reviewing=True, signal_filters=filters)
    return render_template('signals.html', signal_filters=filters)

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
        day = request.args.get('date')
        shanghai = ZoneInfo('Asia/Shanghai')
        if day:
            try:
                if datetime.strptime(day, '%Y-%m-%d').date().isoformat() != day:
                    raise ValueError
            except ValueError:
                return {'error': '日期格式应为 YYYY-MM-DD'}, 400
        limit = max(1, min(1000, int(request.args.get('limit', 1000))))

        db_manager = get_db_manager()
        signals = db_manager.get_strategy_signals(
            strategy_name=strategy_name if strategy_name else None,
            stock_code=stock_code if stock_code else None,
            signal_type=signal_type if signal_type else None,
            status=status if status else None,
            limit=10000 if day or request.args.get('view') == 'opportunities' else limit
        )
        from curs.signal_recorder import local_signals
        merged = {row.get('order_id') or str(row.get('id')): row for row in (signals or [])}
        for row in local_signals():
            if ((strategy_name and row['strategy_name'] != strategy_name)
                    or (stock_code and row['stock_code'] != stock_code)
                    or (signal_type and row['signal_type'] != signal_type)
                    or (status and row['status'] != status)):
                continue
            existing = merged.get(row['order_id'])
            if existing and existing.get('status') == 'SIGNAL_ONLY':
                existing['timestamp'] = row['timestamp']
                existing['mirror_pending'] = row['mirror_pending']
            else:
                merged.setdefault(row['order_id'], row)
        def signal_time(row):
            value = row['timestamp']
            if value.tzinfo is None:
                value = value.replace(tzinfo=shanghai)
            return value.timestamp()
        signals = sorted(merged.values(), key=signal_time, reverse=True)
        if day:
            signals = [row for row in signals if datetime.fromtimestamp(
                signal_time(row), shanghai).date().isoformat() == day]
        raw_count = len(signals)
        if request.args.get('view') == 'opportunities':
            from curs.signal_opportunities import group_opportunities
            signals = group_opportunities(signals)
            for row in signals:
                row['strategy_name'] = '、'.join(row['strategies'])
        signals = signals[:limit]

        # 格式化时间戳
        for signal in signals:
            if 'timestamp' in signal and signal['timestamp']:
                timestamp = signal['timestamp']
                if timestamp.tzinfo is not None:
                    timestamp = timestamp.astimezone(ZoneInfo('Asia/Shanghai'))
                signal['timestamp'] = timestamp.strftime('%Y-%m-%d %H:%M:%S')
            if 'created_at' in signal and signal['created_at']:
                signal['created_at'] = signal['created_at'].strftime('%Y-%m-%d %H:%M:%S')
            if 'updated_at' in signal and signal['updated_at']:
                signal['updated_at'] = signal['updated_at'].strftime('%Y-%m-%d %H:%M:%S')

        return {'signals': signals, 'total': len(signals), 'raw_count': raw_count,
                'view': request.args.get('view', 'raw'), 'window': '最多10000条数据库记录及1000条本地记录；非全库总数'}
    except Exception as e:
        return {'error': str(e)}, 500

@app.route('/api/signals/stats')
def api_signals_stats():
    """获取信号统计数据"""
    try:
        db_manager = get_db_manager()

        # 获取所有信号
        all_signals = db_manager.get_strategy_signals(limit=10000) or []
        from curs.signal_recorder import local_signals
        merged = {row.get('order_id') or str(row.get('id')): row for row in all_signals}
        for row in local_signals(limit=10000):
            merged.setdefault(row['order_id'], row)
        all_signals = list(merged.values())
        from curs.signal_opportunities import group_opportunities
        opportunities = group_opportunities(all_signals)

        # 按策略分组统计
        strategy_stats = {}
        status_stats = {'PENDING': 0, 'EXECUTED': 0, 'CANCELLED': 0, 'SIGNAL_ONLY': 0, 'MIXED': 0, 'UNKNOWN': 0}
        type_stats = {'BUY': 0, 'SELL': 0}

        for signal in all_signals:
            strategy = signal.get('strategy_name', 'unknown')

            if strategy not in strategy_stats:
                strategy_stats[strategy] = 0
            strategy_stats[strategy] += 1

        for signal in opportunities:
            status = signal.get('status', 'unknown')
            signal_type = signal.get('signal_type', 'unknown')

            if status in status_stats:
                status_stats[status] += 1

            if signal_type in type_stats:
                type_stats[signal_type] += 1

        return {
            'strategy_stats': strategy_stats,
            'status_stats': status_stats,
            'type_stats': type_stats,
            'total_signals': len(opportunities),
            'raw_signal_count': len(all_signals),
            'duplicate_triggers': len(all_signals)-len(opportunities),
            'counting_rule': '综合统计按日期+股票+方向；策略计数保留原始触发',
            'window': '最多10000条各来源记录，非全库总数'
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
        db_manager.execute_query(query)
        
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
        from curs.broker.public_quote import get_stock_kline_data
        from collections import defaultdict
        
        # 获取价格类型参数: high(最高价), close(收盘价), avg(均价)
        price_type = request.args.get('price_type', 'high')
        if price_type not in ('high', 'close'):
            return {'error': '公开日线不提供可验证的成交均价，请选择最高价或收盘价'}, 400
        price_cache = {}
        
        db_manager = get_db_manager()
        
        # 获取已执行的买入信号
        signals = db_manager.get_executed_buy_signals(limit=50)
        
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
                if buy_time.tzinfo is not None:
                    buy_time = buy_time.astimezone(ZoneInfo('Asia/Shanghai'))
                if stock_code not in price_cache:
                    price_cache[stock_code] = get_stock_kline_data(stock_code, count=320, adjustment='')
                bars = price_cache[stock_code]
                if not bars or buy_time.strftime('%Y-%m-%d') not in bars['dates']:
                    raise ValueError('公开日线未覆盖实际买入日，不能推算持有天数')
                
                # 获取信号后30天的数据(从T+1开始，即从第2天开始)
                # 如果当天买入，第2天才能卖出
                start_time_str = buy_time.strftime('%Y%m%d') if hasattr(buy_time, 'strftime') else str(buy_time)[:10].replace('-', '')
                
                # 获取更多数据，确保包含T+1之后的数据
                start = bars['dates'].index(buy_time.strftime('%Y-%m-%d'))
                rows = bars['kline_data'][start:start + 35]
                dates = bars['dates'][start:start + 35]
                kline_data = {field: pd.DataFrame([[row[index] for row in rows]], index=[stock_code], columns=dates)
                              for field, index in [('close', 1), ('high', 3)]}
                
                if kline_data and 'close' in kline_data and stock_code in kline_data['close'].index:
                    close_series = kline_data['close'].loc[stock_code]
                    high_series = kline_data['high'].loc[stock_code]

                    # 尝试获取成交量和成交额
                    has_volume = 'volume' in kline_data
                    volume_series = kline_data['volume'].loc[stock_code] if has_volume else None
                    amount_series = kline_data['amount'].loc[stock_code] if 'amount' in kline_data else None
                    
                    max_profit_pct = float('-inf')
                    max_profit_day = 0
                    max_profit_close_pct = float('-inf')
                    
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
                    
                    if not signal_result['daily_profits']:
                        continue
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
            'note': '最近50条历史已执行买入记录；公开不复权日线价格对照，不是已实现收益，最高价不代表可成交。缺失日期不推算。',
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
    return redirect(url_for('manage', section='pool'))

@app.route('/api/stockpool')
def api_stockpool():
    """获取股票池数据"""
    try:
        category = request.args.get('category', '').strip()
        stock = request.args.get('stock', '').strip()
        name = request.args.get('name', '').strip()
        limit = max(1, min(1000, request.args.get('limit', 20, type=int)))
        page = max(1, request.args.get('page', 1, type=int))
        offset = (page - 1) * limit

        db_manager = get_db_manager()
        where = ['is_active = TRUE']
        params = []
        if category:
            where.append('category = %s')
            params.append(category)
        if stock:
            where.append('strpos(lower(stock_code), lower(%s)) > 0')
            params.append(stock)
        if name:
            where.append('strpos(lower(stock_name), lower(%s)) > 0')
            params.append(name)
        conditions = ' AND '.join(where)
        total_result = db_manager.execute_query(
            f'SELECT COUNT(*) AS total FROM stock_pool WHERE {conditions}', tuple(params))
        stocks = db_manager.execute_query(
            f'SELECT * FROM stock_pool WHERE {conditions} ORDER BY added_at DESC, stock_code LIMIT %s OFFSET %s',
            (*params, limit, offset))
        if total_result is None or stocks is None:
            return {'error': '股票池暂时不可用'}, 503
        total = total_result[0]['total']

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

@app.route('/positions')
def positions():
    return redirect(url_for('manage', section='history'))


@app.route('/api/positions')
@app.route('/api/liquidate', methods=['POST'])
@app.route('/api/liquidate/<stock_code>', methods=['POST'])
def retired_positions(stock_code=None):
    return {'error': '持仓和清仓功能已退役，当前服务仅记录信号'}, 410


# ===== 股票详情路由 =====

@app.route('/api/stock/<stock_code>/kline')
def api_stock_kline(stock_code):
    """获取股票K线数据"""
    try:
        if not is_valid_stock_code(stock_code):
            return {'error': '无效的股票代码格式'}, 400

        from curs.broker.public_quote import get_stock_kline_data
        kline_data = get_stock_kline_data(stock_code)
        if kline_data:
            return kline_data
        else:
            return {'error': '未找到股票数据'}, 404

    except Exception as e:
        return {'error': str(e)}, 500

@app.route('/api/stock/<stock_code>/quote')
def api_stock_quote(stock_code):
    """获取股票当日行情"""
    try:
        if not is_valid_stock_code(stock_code):
            return {'error': '无效的股票代码格式'}, 400

        from curs.broker.public_quote import get_stock_quote_data
        quote_data = get_stock_quote_data(stock_code)
        if quote_data:
            return quote_data
        else:
            return {'error': '未找到股票行情数据'}, 404

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
    except Exception:
        today_signals = 0
        pending_signals = 0
        executed_signals = 0

    # 计算收益率（简单计算）
    total_return = 0
    if trades:
        total_return = success_rate

    # 获取实盘状态
    try:
        enabled = db_manager.get_strategy_enabled(strategy_id)
    except Exception:
        enabled = True

    return {
        'id': strategy_id,
        'name': strategy_id.replace('_', ' ').title(),
        'description': f'{strategy_id} 量化交易策略',
        'returns': f'{total_return:.2f}%',
        'details': f'Total trades: {total_trades}, Success rate: {success_rate:.2f}%',
        'return_curve': [trade.get('profit', success_rate/10) for trade in trades[-30:]],
        'holdings': [],
        'positions': trades,
        'signal_stats': {
            'today_signals': today_signals,
            'pending_signals': pending_signals,
            'executed_signals': executed_signals,
            'total_signals': len(signals_stats)
        },
        'enabled': enabled,
    }

@app.route('/')
def index():
    return redirect(url_for('market_sentiment_page'))


# ===== 定时任务管理路由 =====

@app.route('/tasks')
def tasks_page():
    """定时任务管理页面"""
    return redirect(url_for('manage', section='tasks'))


@app.route('/manage')
def manage():
    section = request.args.get('section', 'pool')
    templates = {'pool': 'stockpool.html', 'strategies': 'strategy.html',
                 'tasks': 'tasks.html', 'history': 'history.html'}
    if section not in templates:
        return redirect(url_for('manage'))
    return render_template(templates[section], section=section)

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

@app.route('/api/tasks/<int:task_id>/run', methods=['POST'])
def api_run_task(task_id):
    """立即执行定时任务"""
    try:
        db_manager = get_db_manager()
        task_data = db_manager.get_scheduled_task(task_id)
        if not task_data:
            return {'success': False, 'message': '任务不存在'}, 404

        task_type = task_data.get('task_type', '')
        callback = TASK_CALLBACKS.get(task_type)
        if not callback:
            return {'success': False, 'message': f'不支持的任务类型: {task_type}'}, 400

        config = task_data.get('config', {})
        if isinstance(config, str):
            config = json.loads(config)

        start_time = time.time()
        result = callback(config)
        duration = time.time() - start_time

        db_manager.log_task_execution(
            task_id=task_id,
            status='SUCCESS',
            message=str(result)[:500],
            duration_seconds=round(duration, 2)
        )

        logger.info(f"立即执行任务成功: {task_data.get('name')} ({duration:.2f}秒)")
        return {'success': True, 'message': '任务执行成功', 'result': str(result)[:500], 'duration': round(duration, 2)}
    except Exception as e:
        logger.exception(f"立即执行任务失败: {e}")
        try:
            db_manager = get_db_manager()
            db_manager.log_task_execution(
                task_id=task_id,
                status='FAILED',
                message=str(e)[:500],
                duration_seconds=0
            )
        except Exception:
            pass
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
            {'id': 'collect_hot_stocks', 'name': '东方财富热点股票采集', 'description': '采集东方财富热点股票并同步到股票池', 'config_hint': '无需配置，保持默认即可'},
            {'id': 'sync_hot_stocks', 'name': '同步热点股票', 'description': '从网络获取热点股票并同步到数据库', 'config_hint': '{"category": "hot"}'},
            {'id': 'sync_stock_info', 'name': '同步股票信息', 'description': '从交易账户同步股票基本信息'},
            {'id': 'profit_analysis', 'name': '盈利分析', 'description': '分析策略信号的盈利情况'},
            {'id': 'clear_hot_stocks', 'name': '清除热点股票', 'description': '清除当天添加的热点股票'},
            {'id': 'custom_script', 'name': '自定义脚本任务', 'description': '执行自定义Python脚本', 'config_hint': '{"script_path": "路径/脚本.py", "function_name": "函数名"}'},
        ]
    }


def create_app():
    """创建Flask应用（供外部调用）"""
    return app


if __name__ == "__main__":
    from curs.database import init_db
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
