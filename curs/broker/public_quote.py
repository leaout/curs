# coding: utf-8
"""Public five-level quotes adapted to the existing strategy tick contract."""

import logging
import math
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from curs.database import get_db_manager
from curs.events import EVENT, Event

logger = logging.getLogger(__name__)
SHANGHAI = ZoneInfo('Asia/Shanghai')
_provider = None


def normalize_code(value: str) -> str:
    value = value.strip().upper()
    match = re.fullmatch(r'(\d{6})\.(SH|SZ|BJ)', value)
    if match:
        return value
    match = re.fullmatch(r'(SH|SZ|BJ)(\d{6})', value)
    if match:
        return f'{match[2]}.{match[1]}'
    match = re.fullmatch(r'STOCK_(SH|SZ|BJ)_(\d{6})', value)
    if match:
        return f'{match[2]}.{match[1]}'
    if re.fullmatch(r'\d{6}', value):
        venue = 'SH' if value.startswith(('5', '6', '9')) else 'BJ' if value.startswith(('4', '8')) else 'SZ'
        return f'{value}.{venue}'
    raise ValueError(f'Unsupported stock code: {value}')


def parse_quote(line: str) -> dict:
    match = re.fullmatch(r'v_(sh|sz|bj)(\d{6})="([^"\r\n]+)";?', line.strip())
    if not match:
        raise ValueError('Invalid public quote response')
    values = match[3].split('~')
    if len(values) < 49 or values[2] != match[2]:
        raise ValueError('Missing quote fields')

    def number(index):
        result = float(values[index])
        if not math.isfinite(result) or result < 0:
            raise ValueError(f'Invalid quote field {index}')
        return result

    quote_time = datetime.strptime(values[30], '%Y%m%d%H%M%S').replace(tzinfo=SHANGHAI)
    code = f'{match[2]}.{match[1].upper()}'
    tick = {
        'time': int(quote_time.timestamp() * 1000),
        'lastPrice': number(3), 'lastClose': number(4), 'open': number(5),
        'high': number(33), 'low': number(34),
        'volume': number(6), 'amount': number(37) * 10000,
        'bidPrice': [number(i) for i in range(9, 19, 2)],
        'bidVol': [number(i) for i in range(10, 20, 2)],
        'askPrice': [number(i) for i in range(19, 29, 2)],
        'askVol': [number(i) for i in range(20, 30, 2)],
        'source': 'tencent_public',
    }
    if tick['lastPrice'] <= 0 or tick['lastClose'] <= 0:
        raise ValueError('Suspended or unpriced instrument')
    info = {
        'id': code, 'entity_id': code, 'code': match[2], 'exchange': match[1],
        'name': values[1], 'pre_close': number(4),
        'limit_up_price': number(47), 'limit_down_price': number(48),
    }
    if info['limit_up_price'] <= 0 or info['limit_down_price'] <= 0:
        raise ValueError('No usable daily price limits')
    return {'info': info, 'tick': tick}


class PublicQuoteProvider:
    def __init__(self, timeout_seconds=8):
        self.timeout_seconds = timeout_seconds
        self.records = {}
        self._lock = threading.Lock()

    def _fetch(self, codes):
        symbols = [code.split('.')[1].lower() + code.split('.')[0] for code in codes]
        response = requests.get(
            'https://qt.gtimg.cn/q=' + ','.join(symbols),
            headers={'Referer': 'https://gu.qq.com/'}, timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        records = {}
        for line in response.content.decode('gbk').splitlines():
            try:
                record = parse_quote(line)
                if record['info']['id'] in codes:
                    records[record['info']['id']] = record
            except (ValueError, IndexError):
                logger.warning('Skipping unavailable or invalid public quote')
        return records

    def get_quotes(self, codes):
        codes = sorted({normalize_code(code) for code in codes})
        batches = [codes[i:i + 50] for i in range(0, len(codes), 50)]
        result = {}
        with ThreadPoolExecutor(max_workers=2) as pool:
            for future in [pool.submit(self._fetch, batch) for batch in batches]:
                try:
                    result.update(future.result())
                except (requests.RequestException, UnicodeError):
                    logger.exception('Public quote request failed; retry on next poll')
        with self._lock:
            self.records.update(result)
        return result

    def get_entities(self, codes):
        codes = [normalize_code(code) for code in codes]
        with self._lock:
            missing = [code for code in codes if code not in self.records]
        if missing:
            self.get_quotes(missing)
        with self._lock:
            return [self.records[code]['info'] for code in codes if code in self.records]


def get_provider():
    global _provider
    if _provider is None:
        _provider = PublicQuoteProvider()
    return _provider


def load_stock_pool():
    stocks = get_db_manager().get_hot_stocks_from_pool('hot') or []
    if not stocks:
        path = Path(__file__).resolve().parents[2] / 'data' / 'hotstocks.txt'
        if path.exists():
            stocks = path.read_text(encoding='utf-8').splitlines()
    result = []
    for code in stocks:
        try:
            result.append(normalize_code(code))
        except ValueError:
            logger.warning('Skipping unsupported stock code %s', code)
    return sorted(set(result))


def get_entity_list():
    return get_provider().get_entities(load_stock_pool())


def get_stock_quote_data(stock_code):
    stock_code = normalize_code(stock_code)
    record = get_provider().get_quotes([stock_code]).get(stock_code)
    if not record:
        return None
    tick, info = record['tick'], record['info']
    change = tick['lastPrice'] - tick['lastClose']
    return {'stock_code': stock_code, 'name': info['name'], 'price': tick['lastPrice'],
            'change': change, 'change_percent': change / tick['lastClose'] * 100,
            'volume': tick['volume'], 'amount': tick['amount'], 'high': tick['high'],
            'low': tick['low'], 'open': tick['open'], 'close': tick['lastClose'],
            'turnover': None, 'pe': None, 'market_cap': None, 'source': tick['source'],
            'update_time': datetime.fromtimestamp(tick['time'] / 1000, SHANGHAI).strftime('%Y-%m-%d %H:%M:%S')}


def get_stock_kline_data(stock_code, count=60, adjustment='qfq'):
    if adjustment not in ('', 'qfq', 'hfq'):
        raise ValueError('Unsupported price adjustment')
    code, exchange = normalize_code(stock_code).split('.')
    symbol = exchange.lower() + code
    response = requests.get('https://web.ifzq.gtimg.cn/appstock/app/fqkline/get',
                            params={'param': f'{symbol},day,,,{count},{adjustment}'}, timeout=8)
    response.raise_for_status()
    payload = response.json()
    if payload.get('code') != 0:
        raise ValueError('Public daily bars unavailable')
    instrument = payload.get('data', {}).get(symbol, {})
    rows = (instrument.get(adjustment + 'day') or instrument.get('day') or [])[-count:]
    dates, candles, volumes = [], [], []
    for row in rows:
        datetime.strptime(row[0], '%Y-%m-%d')
        prices = [float(row[i]) for i in (1, 2, 4, 3)]
        if not all(math.isfinite(price) and price > 0 for price in prices):
            raise ValueError('Invalid public daily bar')
        dates.append(row[0])
        candles.append(prices)
        volumes.append(float(row[5]))
    return {'stock_code': normalize_code(stock_code), 'dates': dates, 'kline_data': candles,
            'volumes': volumes, 'source': 'tencent_public'} if rows else None


class PublicQuoteEngine:
    def __init__(self, event_bus, config=None):
        self.event_bus = event_bus
        config = config or {}
        self.interval = max(3, float(config.get('poll_interval_seconds', 5)))
        self.max_age = float(config.get('max_quote_age_seconds', 120))
        self.provider = get_provider()
        self.provider.timeout_seconds = float(config.get('timeout_seconds', 8))
        self.stocks = []
        self._stop = threading.Event()
        self._thread = None
        self._last_times = {}
        self._day = None
        self._count = 0
        self.min_coverage = float(config.get('min_coverage', .8))
        self._health = {'data_ready': False, 'coverage': 0, 'consecutive_failures': 0,
                        'last_success': None, 'last_attempt': None, 'reason': '尚未收到有效行情'}
        self._observation_minute = None
        self._resync_required = False
        from curs.first_board import FirstBoardMonitor
        self.first_board = FirstBoardMonitor(config.get('first_board', {}))

    def reload_stock_pool(self):
        self.stocks = load_stock_pool()
        logger.info('Public quote stock pool: %s instruments', len(self.stocks))

    def poll_once(self, now=None):
        supplied_now = now
        now = now or datetime.now(SHANGHAI)
        if now.weekday() >= 5 or not ('09:30' <= now.strftime('%H:%M') <= '11:30' or '13:00' <= now.strftime('%H:%M') <= '15:00'):
            return {}
        new_day = self._day != now.date()
        if new_day:
            self.reload_stock_pool()
            self._last_times.clear()
            self._day = now.date()
        if not self.stocks:
            self.reload_stock_pool()
            return {}
        from curs.signal_observer import observe, watch_codes
        records = self.provider.get_quotes(sorted(set(self.stocks) | set(watch_codes())))
        if new_day:
            self.event_bus.put_event(Event(EVENT.BEFORE_TRADING))
        reference_time = supplied_now or datetime.now(SHANGHAI)
        ticks = {}
        fresh = {}
        for code, record in records.items():
            tick = record['tick']
            quoted_at = datetime.fromtimestamp(tick['time'] / 1000, SHANGHAI)
            if quoted_at.date() != now.date() or not 0 <= (reference_time - quoted_at).total_seconds() <= self.max_age:
                continue
            fresh[code] = record
            if tick['time'] <= self._last_times.get(code, 0):
                continue
            self._last_times[code] = tick['time']
            ticks[code] = tick
        coverage = sum(code in fresh for code in self.stocks) / len(self.stocks)
        ready = coverage >= self.min_coverage
        self._health.update(data_ready=ready, coverage=coverage, last_attempt=reference_time.isoformat(),
                            consecutive_failures=0 if ready else self._health['consecutive_failures'] + 1,
                            reason='行情有效' if ready else '新鲜行情覆盖率不足，暂停策略事件')
        if ready:
            self._health['last_success'] = reference_time.isoformat()
        minute = reference_time.isoformat(timespec='minutes')
        if minute != self._observation_minute:
            try:
                observe(reference_time, fresh, self.stocks, self._health)
                self._observation_minute = minute
            except Exception:
                logger.exception('Forward observation failed; strategy quotes remain independent')
        ticks = {code: tick for code, tick in ticks.items() if code in self.stocks}
        try:
            self.first_board.scan(reference_time, {code: row for code, row in fresh.items() if code in self.stocks}, ready)
        except Exception:
            logger.exception('First-board monitor failed; legacy strategies remain independent')
        if not ready:
            self._resync_required = True
            return {}
        if self._resync_required:
            self.event_bus.put_event(Event(EVENT.BEFORE_TRADING))
            self._resync_required = False
        if ticks:
            self._count += 1
            self.event_bus.put_event(Event(EVENT.TICK, tick=ticks))
        return ticks

    def _run(self):
        while not self._stop.is_set():
            try:
                self.poll_once()
            except Exception:
                logger.exception('Public quote scan failed; retry on next poll')
            self._stop.wait(self.interval)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self.reload_stock_pool()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name='PublicQuote', daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=10)

    def get_stats(self):
        now = datetime.now(SHANGHAI)
        active = now.weekday() < 5 and ('09:30' <= now.strftime('%H:%M') <= '11:30' or '13:00' <= now.strftime('%H:%M') <= '15:00')
        health = dict(self._health)
        last = health['last_success']
        if not active:
            health.update(data_ready=False, reason='非交易时段；显示最近采集记录')
        elif not last or (now - datetime.fromisoformat(last)).total_seconds() > self.max_age:
            health.update(data_ready=False, reason='行情过期或尚未采集成功')
        return dict(health, provider='tencent_public', subscribed_stocks=len(self.stocks),
                    total_ticks=self._count, running=bool(self._thread and self._thread.is_alive()),
                    session='active' if active else 'outside_session', scope='hot_pool')
