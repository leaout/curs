# coding: utf-8
"""Hot-stock focused public research collection and agent report storage."""

import argparse
import hashlib
import json
import logging
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
_MAX_STOCKS = 100
_SHANGHAI = ZoneInfo('Asia/Shanghai')
_DAILY_MAX_ATTEMPTS = 3


def _db_path():
    root = Path(__file__).resolve().parents[1]
    path = Path(os.environ.get('CURS_STOCK_INTEL_DB', root / 'data' / 'stock_intel.sqlite3'))
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _connect():
    con = sqlite3.connect(str(_db_path()), timeout=10)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA journal_mode=WAL')
    con.executescript('''
        CREATE TABLE IF NOT EXISTS intel_items (
          id TEXT PRIMARY KEY, stock_code TEXT NOT NULL, stock_name TEXT NOT NULL,
          direction TEXT NOT NULL, platform TEXT NOT NULL, title TEXT NOT NULL,
          excerpt TEXT NOT NULL DEFAULT '', url TEXT NOT NULL, published_at TEXT,
          collected_at TEXT NOT NULL, UNIQUE(platform, url, stock_code)
        );
        CREATE INDEX IF NOT EXISTS ix_intel_stock_time ON intel_items(stock_code, collected_at);
        CREATE TABLE IF NOT EXISTS intel_runs (
          id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT NOT NULL,
          finished_at TEXT, status TEXT NOT NULL, summary TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS agent_reports (
          id TEXT PRIMARY KEY, stock_code TEXT NOT NULL, stock_name TEXT NOT NULL,
          created_at TEXT NOT NULL, agent TEXT NOT NULL, assessment TEXT NOT NULL,
          evidence TEXT NOT NULL, counter_evidence TEXT NOT NULL,
          catalysts TEXT NOT NULL, invalidation TEXT NOT NULL,
          source_ids TEXT NOT NULL, imported_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_reports_time ON agent_reports(created_at);
        CREATE TABLE IF NOT EXISTS desktop_daily_reports (
          report_day TEXT NOT NULL, stock_code TEXT NOT NULL, report_id TEXT,
          attempts INTEGER NOT NULL DEFAULT 0,
          PRIMARY KEY(report_day, stock_code)
        );
        CREATE TABLE IF NOT EXISTS desktop_market_reports (
          report_day TEXT PRIMARY KEY, attempts INTEGER NOT NULL DEFAULT 0,
          report TEXT
        );
    ''')
    return con


def _now():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')


def _hot_pool():
    from curs.database import get_db_manager
    try:
        from curs.stock_names import stock_catalog
        catalog = stock_catalog()
    except Exception:
        logger.exception('Unable to load local stock name catalogue')
        catalog = {}
    try:
        codes = get_db_manager().get_top_ranked_hot_stocks(_MAX_STOCKS) or []
    except Exception:
        logger.exception('Unable to load database hot-stock pool')
        codes = []
    return [{'stock_code': code, 'stock_name': catalog.get(code) or ''} for code in codes]


def _safe_link(value):
    try:
        parsed = urlparse(value)
        return parsed.scheme == 'https' and bool(parsed.hostname)
    except (TypeError, ValueError):
        return False


def _store_item(con, item):
    fingerprint = hashlib.sha256('|'.join((item['stock_code'], item['platform'], item['url'])).encode('utf-8')).hexdigest()[:24]
    con.execute('''INSERT OR IGNORE INTO intel_items
      (id,stock_code,stock_name,direction,platform,title,excerpt,url,published_at,collected_at)
      VALUES (?,?,?,?,?,?,?,?,?,?)''', (fingerprint, item['stock_code'], item['stock_name'], item['direction'],
      item['platform'], item['title'], item['excerpt'], item['url'], item.get('published_at'), _now()))
    return fingerprint


def _read_market_report(con, report_day):
    row = con.execute('''SELECT report_day, report FROM desktop_market_reports
        WHERE report IS NOT NULL AND (? IS NULL OR report_day = ?)
        ORDER BY report_day DESC LIMIT 1''', (report_day, report_day)).fetchone()
    return {**json.loads(row['report']), 'report_day': row['report_day']} if row else None


def market_report(report_day):
    con = _connect()
    try:
        return _read_market_report(con, report_day)
    finally:
        con.close()


def board_report(force=False, report_day=None):
    pool = _hot_pool()
    con = _connect()
    try:
        daily = None
        market = _read_market_report(con, report_day)
        if report_day:
            daily = dict(con.execute('''SELECT COUNT(*) AS total, COUNT(report_id) AS complete
                FROM desktop_daily_reports WHERE report_day=?''', (report_day,)).fetchone())
            scheduled = con.execute('''SELECT agent_reports.* FROM agent_reports
                JOIN desktop_daily_reports ON desktop_daily_reports.report_id = agent_reports.id
                WHERE desktop_daily_reports.report_day = ?''', (report_day,)).fetchall()
            # Include manual and imported reports created on the selected Shanghai date.
            begin = datetime.fromisoformat(report_day).replace(tzinfo=_SHANGHAI)
            end = begin + timedelta(days=1)
            dated = con.execute('''SELECT * FROM agent_reports
                WHERE julianday(created_at) >= julianday(?) AND julianday(created_at) < julianday(?)
                AND NOT EXISTS (SELECT 1 FROM desktop_daily_reports WHERE report_id = agent_reports.id)
                ORDER BY created_at DESC''', (begin.isoformat(), end.isoformat())).fetchall()
            reports = list({row['id']: dict(row) for row in (*scheduled, *dated)}.values())
        else:
            reports = [dict(row) for row in con.execute('''SELECT * FROM agent_reports
                ORDER BY created_at DESC LIMIT 100''').fetchall()]
        reports.sort(key=lambda row: row['created_at'], reverse=True)
        source_ids = set()
        for row in reports:
            for key in ('evidence', 'counter_evidence', 'catalysts', 'source_ids', 'invalidation'):
                row[key] = json.loads(row[key])
            source_ids.update(row['source_ids'])
        items_by_id = {}
        ids = sorted(source_ids)
        for offset in range(0, len(ids), 500):
            chunk = ids[offset:offset + 500]
            query = 'SELECT * FROM intel_items WHERE id IN (' + ','.join('?' for _ in chunk) + ')'
            items_by_id.update((row['id'], dict(row)) for row in con.execute(query, chunk))
        if not report_day:
            cutoff = (datetime.now().astimezone() - timedelta(days=14)).isoformat(timespec='seconds')
            for row in con.execute('''SELECT * FROM intel_items
                    WHERE collected_at >= ? ORDER BY collected_at DESC LIMIT 250''', (cutoff,)):
                items_by_id.setdefault(row['id'], dict(row))
        items = sorted(items_by_id.values(), key=lambda row: row['collected_at'], reverse=True)
        latest = con.execute('SELECT * FROM intel_runs ORDER BY id DESC LIMIT 1').fetchone()
    finally:
        con.close()
    return {'pool': pool, 'items': items, 'agent_reports': reports, 'daily': daily,
            'market_report': market,
            'latest_run': dict(latest) if latest else None,
            }


def import_agent_report(path):
    """Import a structured local agent result, requiring citations to collected item IDs."""
    with open(path, 'r', encoding='utf-8') as source:
        payload = json.load(source)
    return save_agent_report(payload)


def daily_pending(report_day, codes):
    """Keep the scheduled roster across restarts and return unfinished codes."""
    con = _connect()
    try:
        with con:
            con.execute('BEGIN IMMEDIATE')
            rows = con.execute('''SELECT stock_code, report_id, attempts FROM desktop_daily_reports
                WHERE report_day=? ORDER BY rowid''', (report_day,)).fetchall()
            if not rows:
                con.executemany('INSERT INTO desktop_daily_reports (report_day, stock_code) VALUES (?,?)',
                                ((report_day, code) for code in codes))
                return codes
            return [row['stock_code'] for row in rows if row['report_id'] is None
                    and row['attempts'] < _DAILY_MAX_ATTEMPTS]
    finally:
        con.close()


def mark_daily_attempt(report_day, code):
    con = _connect()
    try:
        with con:
            con.execute('''UPDATE desktop_daily_reports SET attempts=attempts+1
                WHERE report_day=? AND stock_code=?''', (report_day, code))
    finally:
        con.close()


def market_report_pending(report_day):
    con = _connect()
    try:
        row = con.execute('SELECT attempts, report FROM desktop_market_reports WHERE report_day=?',
                          (report_day,)).fetchone()
        return row is None or (row['report'] is None and row['attempts'] < _DAILY_MAX_ATTEMPTS)
    finally:
        con.close()


def claim_market_report(report_day):
    con = _connect()
    try:
        with con:
            return con.execute('''INSERT INTO desktop_market_reports (report_day, attempts)
                VALUES (?, 1) ON CONFLICT(report_day) DO UPDATE SET attempts=attempts+1
                WHERE report IS NULL AND attempts < ?''',
                               (report_day, _DAILY_MAX_ATTEMPTS)).rowcount == 1
    finally:
        con.close()


def save_market_report(report_day, report):
    if not isinstance(report, dict):
        raise ValueError('Invalid market report')
    assessment = report.get('assessment')
    if not isinstance(assessment, str) or not assessment.strip():
        raise ValueError('Missing market assessment')
    sources = _desktop_sources(report)
    payload = {'assessment': assessment.strip()[:6000], 'sources': sources,
               'created_at': datetime.now(_SHANGHAI).isoformat()}
    con = _connect()
    try:
        with con:
            con.execute('''UPDATE desktop_market_reports SET report=?
                WHERE report_day=? AND report IS NULL''',
                        (json.dumps(payload, ensure_ascii=False), report_day))
    finally:
        con.close()


def _desktop_sources(report):
    sources = report.get('sources')
    if not isinstance(sources, list) or not sources:
        raise RuntimeError('WorkBuddy 未返回来源，报告未保存')
    valid = []
    for source in sources[:20]:
        if (not isinstance(source, dict) or not isinstance(source.get('url'), str)
                or not _safe_link(source['url']) or not source.get('title')):
            raise ValueError('Invalid research source')
        valid.append({'title': str(source['title'])[:500], 'url': source['url'],
                      'excerpt': str(source.get('excerpt', ''))[:1200]})
    return valid


def save_desktop_report(code, report, report_day=None):
    if not isinstance(report, dict):
        raise ValueError('Invalid research report')
    name = next((row['stock_name'] for row in _hot_pool() if row['stock_code'] == code), '')
    required_lists = ('evidence', 'counter_evidence', 'catalysts', 'invalidation')
    assessment = report.get('assessment')
    if not isinstance(assessment, str) or not assessment.strip():
        raise ValueError('Missing assessment')
    if any(not isinstance(report.get(key), list) or
           not all(isinstance(value, str) for value in report[key]) for key in required_lists):
        raise ValueError('Invalid research fields')
    platform = 'WorkBuddy Desktop Bridge'
    items = [{**source, 'stock_code': code, 'stock_name': name, 'direction': 'agent_research',
              'platform': platform} for source in _desktop_sources(report)]
    entry = {'stock_code': code, 'assessment': assessment,
             **{key: report[key] for key in required_lists}}
    payload = {'agent': platform, 'created_at': datetime.now(_SHANGHAI).isoformat(), 'items': [entry]}
    return save_agent_report(payload, pool={code: name}, sources=items, report_day=report_day)


def save_agent_report(payload, pool=None, allowed_ids=None, sources=(), report_day=None):
    """Validate and atomically persist reports from a local file or an agent."""
    entries = payload.get('items')
    if not isinstance(entries, list) or not entries:
        raise ValueError('JSON 必须包含非空 items 数组')
    if pool is None:
        pool = {row['stock_code']: row['stock_name'] for row in _hot_pool()}
    con = _connect()
    inserted = 0
    try:
        if sources:
            entries[0]['source_ids'] = list(dict.fromkeys(_store_item(con, item) for item in sources))
        for item in entries:
            code = item.get('stock_code')
            if code not in pool:
                raise ValueError('股票不在当前数据库热点池: {}'.format(code))
            source_ids = item.get('source_ids')
            if not isinstance(source_ids, list) or not source_ids:
                raise ValueError('{} 缺少 source_ids，分析必须引用已采集材料'.format(code))
            if allowed_ids is not None and not set(source_ids).issubset(allowed_ids):
                raise ValueError('{} 引用了本次任务之外的材料'.format(code))
            refs = con.execute('SELECT id,stock_code FROM intel_items WHERE id IN ({})'.format(','.join('?' for _ in source_ids)), source_ids).fetchall()
            if len(refs) != len(set(source_ids)) or any(ref['stock_code'] != code for ref in refs):
                raise ValueError('{} 引用了不存在或不属于该股票的情报来源'.format(code))
            required = ('assessment', 'evidence', 'counter_evidence', 'catalysts', 'invalidation')
            if any(key not in item for key in required):
                raise ValueError('{} 缺少分析必需字段'.format(code))
            identity = [item, payload['created_at']] if sources else item
            report_id = hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:24]
            con.execute('''INSERT OR REPLACE INTO agent_reports VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                (report_id, code, pool[code], payload.get('created_at') or _now(), payload.get('agent') or '外部智能体',
                 str(item['assessment'])[:4000], json.dumps(item['evidence'], ensure_ascii=False),
                 json.dumps(item['counter_evidence'], ensure_ascii=False), json.dumps(item['catalysts'], ensure_ascii=False),
                 json.dumps(item['invalidation'], ensure_ascii=False), json.dumps(source_ids), _now()))
            if report_day:
                con.execute('''UPDATE desktop_daily_reports SET report_id=?
                    WHERE report_day=? AND stock_code=?''', (report_id, report_day, code))
            inserted += 1
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return inserted


def main():
    parser = argparse.ArgumentParser(description='热点股情报工具')
    parser.add_argument('--import-agent-report', metavar='JSON', help='导入外部智能体结构化分析报告')
    args = parser.parse_args()
    if args.import_agent_report:
        print('已导入 {} 条分析'.format(import_agent_report(args.import_agent_report)))
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
