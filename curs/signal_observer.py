# coding: utf-8
"""Local forward observations, not simulated fills or investment returns."""

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from curs import signal_recorder as journal


def connect():
    db = journal._connect()
    db.executescript('''
        CREATE TABLE IF NOT EXISTS market_observations (
            minute TEXT PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS signal_context (
            order_id TEXT PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS signal_observations (
            order_id TEXT NOT NULL, day TEXT NOT NULL, first_time TEXT NOT NULL,
            last_time TEXT NOT NULL, first_price REAL NOT NULL, last_price REAL NOT NULL,
            max_price REAL NOT NULL, min_price REAL NOT NULL, samples INTEGER NOT NULL,
            PRIMARY KEY(order_id, day));
    ''')
    return db


def watch_codes():
    if not journal.JOURNAL_PATH.exists():
        return []
    with journal._lock:
        db = connect()
        try:
            return [row[0] for row in db.execute(
                "SELECT DISTINCT stock_code FROM signals WHERE signal_type='BUY' AND trade_date >= date('now', '-30 days')")]
        finally:
            db.close()


def capture_context(order_id, now):
    """Preserve only a recently observed environment; never borrow future data."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=ZoneInfo('Asia/Shanghai'))
    with journal._lock:
        db = connect()
        try:
            row = db.execute('SELECT minute, payload FROM market_observations WHERE minute<=? ORDER BY minute DESC LIMIT 1',
                             (now.isoformat(timespec='minutes'),)).fetchone()
            payload = {'state': 'unknown', 'reason': 'No recent environment snapshot'}
            if row:
                minute = datetime.fromisoformat(row['minute'])
                if minute.tzinfo is None:
                    minute = minute.replace(tzinfo=now.tzinfo)
                candidate = json.loads(row['payload'])
                observed_at = datetime.fromisoformat(candidate.get('observed_at') or candidate.get('last_attempt') or row['minute'])
                if observed_at.tzinfo is None:
                    observed_at = observed_at.replace(tzinfo=now.tzinfo)
                if 0 <= (now - observed_at).total_seconds() <= 120:
                    payload = candidate
            db.execute('INSERT OR IGNORE INTO signal_context VALUES (?, ?)',
                       (order_id, json.dumps(payload, ensure_ascii=False)))
            db.commit()
        finally:
            db.close()


def observe(now, fresh, pool, health):
    """One-minute persistence; extrema use post-signal last prices, not daily high/low."""
    minute = now.isoformat(timespec='minutes')
    pool_records = [fresh[code] for code in pool if code in fresh]
    count = len(pool_records)
    up = sum(abs(r['tick']['lastPrice'] - r['info']['limit_up_price']) < .005 for r in pool_records)
    down = sum(abs(r['tick']['lastPrice'] - r['info']['limit_down_price']) < .005 for r in pool_records)
    touched = sum(r['tick']['high'] >= r['info']['limit_up_price'] - .005 for r in pool_records)
    payload = dict(health, scope='hot_pool', observed_at=now.isoformat(), observed=count, limit_up=up, limit_down=down,
                   touched_limit_up=touched, opened_limit_up=max(0, touched - up),
                   opened_ratio=(touched - up) / touched if touched else None,
                   state='observe_only' if health['data_ready'] else 'data_unavailable',
                   decision='第一版仅记录环境，不据此判定市场可交易')
    with journal._lock:
        db = connect()
        try:
            db.execute('INSERT OR REPLACE INTO market_observations VALUES (?, ?)',
                       (minute, json.dumps(payload, ensure_ascii=False)))
            for row in db.execute("SELECT * FROM signals WHERE signal_type='BUY' AND trade_date >= date(?, '-30 days')",
                                  (now.date().isoformat(),)).fetchall():
                record = fresh.get(row['stock_code'])
                if not record:
                    continue
                quoted = datetime.fromtimestamp(record['tick']['time'] / 1000, now.tzinfo)
                triggered = datetime.fromisoformat(row['timestamp'])
                if triggered.tzinfo is None:
                    triggered = triggered.replace(tzinfo=now.tzinfo)
                if quoted <= triggered:
                    continue
                price = record['tick']['lastPrice']
                db.execute('''INSERT INTO signal_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                    ON CONFLICT(order_id, day) DO UPDATE SET
                    last_time=excluded.last_time, last_price=excluded.last_price,
                    max_price=MAX(max_price, excluded.max_price), min_price=MIN(min_price, excluded.min_price),
                    samples=samples+1 WHERE excluded.last_time > last_time''',
                           (row['order_id'], quoted.date().isoformat(), quoted.isoformat(), quoted.isoformat(),
                            price, price, price, price))
            db.commit()
        finally:
            db.close()


def report(limit=100):
    with journal._lock:
        db = connect()
        try:
            environments = [json.loads(r['payload']) | {'minute': r['minute']} for r in db.execute(
                'SELECT * FROM market_observations ORDER BY minute DESC LIMIT 60')]
            signals = []
            selected = db.execute('''SELECT trade_date,stock_code,signal_type FROM signals
                GROUP BY trade_date,stock_code,signal_type ORDER BY MAX(timestamp) DESC LIMIT ?''', (limit,)).fetchall()
            rows = []
            for key in selected:
                rows.extend(db.execute('SELECT * FROM signals WHERE trade_date=? AND stock_code=? AND signal_type=?', tuple(key)).fetchall())
            for row in rows:
                item = dict(row)
                context = db.execute('SELECT payload FROM signal_context WHERE order_id=?', (row['order_id'],)).fetchone()
                item['environment'] = json.loads(context[0]) if context else None
                observations = [dict(r) for r in db.execute(
                    'SELECT * FROM signal_observations WHERE order_id=? ORDER BY day', (row['order_id'],))]
                for sample in observations:
                    for field in ('first_price', 'last_price', 'max_price', 'min_price'):
                        sample[field + '_change_pct'] = (sample[field] / row['price'] - 1) * 100
                item['observations'] = observations
                item['execution'] = '未确认成交，仅信号参考价比较'
                signals.append(item)
            from curs.signal_opportunities import group_opportunities
            opportunities = group_opportunities(signals)
            return {'environments': environments, 'signals': signals, 'opportunities': opportunities,
                    'summary': {'opportunity_count': len(opportunities), 'raw_signal_count': len(signals),
                                'duplicate_triggers': len(signals)-len(opportunities)},
                    'scope': 'hot_pool', 'reference_rule': '综合观察使用最早信号；策略展开各自独立计算'}
        finally:
            db.close()
