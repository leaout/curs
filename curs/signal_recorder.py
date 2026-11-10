# coding: utf-8
"""Durable, daily deduplicated signals with a PostgreSQL mirror for the Web UI."""

import logging
import math
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from curs.database import get_db_manager

logger = logging.getLogger(__name__)
JOURNAL_PATH = Path(__file__).resolve().parents[1] / 'data' / 'strategy_records' / 'signals.sqlite3'
_lock = threading.RLock()
_mirror_lock = threading.Lock()


class SignalMirror:
    """Independent retry worker; database latency never runs in strategy callbacks."""
    def __init__(self):
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name='SignalMirror', daemon=True)
        self._thread.start()

    def _run(self):
        while not self._stop.is_set():
            flush_pending_signals()
            self._stop.wait(5)

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)


def local_signals(limit=1000):
    if not JOURNAL_PATH.exists():
        return []
    with _lock:
        db = _connect()
        try:
            rows = [dict(row) for row in db.execute('SELECT * FROM signals ORDER BY timestamp DESC LIMIT ?', (limit,))]
            for row in rows:
                row['timestamp'] = datetime.fromisoformat(row['timestamp'])
                row['status'] = 'SIGNAL_ONLY'
                row['mirror_pending'] = not bool(row['mirrored'])
            return rows
        finally:
            db.close()


def _connect():
    JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(JOURNAL_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute('''CREATE TABLE IF NOT EXISTS signals (
        order_id TEXT PRIMARY KEY, trade_date TEXT NOT NULL, timestamp TEXT NOT NULL,
        strategy_name TEXT NOT NULL, stock_code TEXT NOT NULL, signal_type TEXT NOT NULL,
        price REAL NOT NULL, volume INTEGER NOT NULL, mirrored INTEGER NOT NULL DEFAULT 0,
        UNIQUE(trade_date, strategy_name, stock_code, signal_type)
    )''')
    if 'stock_name' not in {row[1] for row in db.execute('PRAGMA table_info(signals)')}:
        db.execute('ALTER TABLE signals ADD COLUMN stock_name TEXT')
        db.commit()
    return db


def flush_pending_signals():
    if not JOURNAL_PATH.exists():
        return
    if not _mirror_lock.acquire(blocking=False):
        return
    try:
        with _lock:
            db = _connect()
            try:
                pending = [dict(row) for row in db.execute('SELECT * FROM signals WHERE mirrored=0 ORDER BY timestamp LIMIT 20')]
            finally:
                db.close()
        for row in pending:
            manager = get_db_manager()
            existing = manager.execute_query('SELECT id FROM strategy_signals WHERE order_id=%s', (row['order_id'],))
            if existing is None:
                break
            saved = bool(existing) or manager.save_strategy_signal(
                strategy_name=row['strategy_name'], stock_code=row['stock_code'], signal_type=row['signal_type'],
                price=row['price'], volume=row['volume'], order_id=row['order_id'], status='SIGNAL_ONLY',
                timestamp=datetime.fromisoformat(row['timestamp']), stock_name=row['stock_name'])
            if not saved:
                break
            with _lock:
                db = _connect()
                try:
                    db.execute('UPDATE signals SET mirrored=1 WHERE order_id=?', (row['order_id'],))
                    db.commit()
                finally:
                    db.close()
    except Exception:
        logger.exception('Signal is saved locally; PostgreSQL mirror will retry')
    finally:
        _mirror_lock.release()


def record_signal(context, strategy_name, stock_code, price, volume, signal_type='BUY'):
    if not math.isfinite(price) or not math.isfinite(volume) or price <= 0 or volume <= 0 or signal_type not in ('BUY', 'SELL'):
        return False
    timestamp = context.current_time or datetime.now(ZoneInfo('Asia/Shanghai'))
    timestamp = (timestamp.replace(tzinfo=ZoneInfo('Asia/Shanghai')) if timestamp.tzinfo is None
                 else timestamp.astimezone(ZoneInfo('Asia/Shanghai')))
    name = None
    try:
        from curs.stock_names import cached_name
        name = getattr(context, 'stock_base_info', {}).get(stock_code, {}).get('name') or cached_name(stock_code)
    except Exception:
        logger.exception('Stock name lookup failed; signal recording remains available')
    with _lock:
        db = _connect()
        try:
            result = db.execute('''INSERT OR IGNORE INTO signals
                (order_id, trade_date, timestamp, strategy_name, stock_code, signal_type, price, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (str(uuid4()), timestamp.strftime('%Y-%m-%d'), timestamp.isoformat(),
                 strategy_name, stock_code, signal_type, price, volume))
            created = result.rowcount > 0
            order_id = db.execute('SELECT order_id FROM signals WHERE trade_date=? AND strategy_name=? AND stock_code=? AND signal_type=?',
                                  (timestamp.strftime('%Y-%m-%d'), strategy_name, stock_code, signal_type)).fetchone()[0]
            db.commit()
            if created:
                db.execute('UPDATE signals SET stock_name=? WHERE order_id=?', (name, order_id))
                db.commit()
        finally:
            db.close()
        if created:
            from curs.signal_observer import capture_context
            try:
                capture_context(order_id, timestamp)
            except Exception:
                logger.exception('Signal saved, but environment context could not be recorded')
    if created:
        logger.info('仅信号已保存: %s %s %s price=%s volume=%s', strategy_name, signal_type, stock_code, price, volume)
    return True
