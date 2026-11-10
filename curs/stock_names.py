# coding: utf-8
"""Shared display names from local security metadata; no network fetch on page reads."""

import logging
import re
import threading
import time

from curs.database import get_db_manager

logger = logging.getLogger(__name__)
_cache = {}
_loaded = 0
_lock = threading.Lock()


def cached_name(code):
    from curs.broker.public_quote import get_provider
    record = get_provider().records.get(code)
    return record['info'].get('name') if record else _cache.get(code)


def names_for(codes):
    global _loaded
    codes = {c for c in codes if isinstance(c, str) and re.fullmatch(r'\d{6}\.(SH|SZ|BJ)', c)}
    with _lock:
        if time.monotonic() - _loaded > 120:
            db = get_db_manager()
            for table in ('stock_pool', 'stock_info'):
                rows = db.execute_query(f'SELECT stock_code, stock_name FROM {table} WHERE stock_name IS NOT NULL') or []
                for row in rows:
                    if row['stock_name']:
                        _cache[row['stock_code']] = row['stock_name']
            try:
                from curs.market_sentiment import stored
                from datetime import datetime
                from curs.broker.public_quote import SHANGHAI
                universe = stored('market_universe', datetime.now(SHANGHAI).date().isoformat())
                if universe:
                    _cache.update({code: entry['name'] for code, entry in universe['securities'].items()})
            except Exception:
                logger.exception('Local universe name lookup failed')
            _loaded = time.monotonic()
        from curs.broker.public_quote import get_provider
        for code in codes:
            record = get_provider().records.get(code)
            if record and record['info'].get('name'):
                _cache[code] = record['info']['name']
        return {code: _cache.get(code) for code in codes}


def enrich(payload):
    rows = []

    def walk(value):
        if isinstance(value, dict):
            code = value.get('stock_code') or value.get('code')
            if isinstance(code, str) and re.fullmatch(r'\d{6}\.(SH|SZ|BJ)', code):
                rows.append((value, code))
            for child in list(value.values()):
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(payload)
    if rows:
        names = names_for([code for row, code in rows])
        for row, code in rows:
            name = row.get('stock_name') or names.get(code)
            row['stock_name'] = name
            row['stock_label'] = f'{code} {name or "名称暂缺"}'
    return payload


def stock_catalog():
    """Return known local names only; no remote name discovery."""
    names_for([])
    with _lock:
        return dict(_cache)
