# coding: utf-8
"""Independent A-share snapshots with explicit coverage and frozen prior cohorts."""

import json
import logging
import statistics
import threading
from datetime import datetime

import requests

from curs import signal_recorder as journal
from curs.broker.public_quote import PublicQuoteProvider, SHANGHAI, get_stock_kline_data

logger = logging.getLogger(__name__)


def connect():
    db = journal._connect()
    db.executescript('''
        CREATE TABLE IF NOT EXISTS market_universe (day TEXT PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS market_cohorts (day TEXT PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sentiment_snapshots (timestamp TEXT PRIMARY KEY, payload TEXT NOT NULL);
    ''')
    return db


def persist(table, key, value, immutable=False):
    if table not in ('market_universe', 'market_cohorts', 'sentiment_snapshots'):
        raise ValueError('Invalid journal table')
    column = 'timestamp' if table == 'sentiment_snapshots' else 'day'
    with journal._lock:
        db = connect()
        try:
            verb = 'IGNORE' if immutable else 'REPLACE'
            db.execute(f'INSERT OR {verb} INTO {table} ({column}, payload) VALUES (?, ?)',
                       (key, json.dumps(value, ensure_ascii=False)))
            db.commit()
        finally:
            db.close()


def stored(table, key):
    if table not in ('market_universe', 'market_cohorts'):
        raise ValueError('Invalid journal table')
    with journal._lock:
        db = connect()
        try:
            row = db.execute(f'SELECT payload FROM {table} WHERE day=?', (key,)).fetchone()
            return json.loads(row[0]) if row else None
        finally:
            db.close()


def board(code):
    if code.endswith('.BJ'):
        return 'beijing'
    if code.startswith(('688', '689')):
        return 'star'
    if code.startswith(('300', '301', '302')):
        return 'chinext'
    return 'main'


def a_share_code(raw, venue):
    if not isinstance(raw, str) or len(raw) != 6 or not raw.isdigit():
        raise ValueError('Invalid security code')
    if raw.startswith(('4', '8', '92')):
        return raw + '.BJ'
    if venue == 1 and raw.startswith(('600', '601', '603', '605', '688', '689')):
        return raw + '.SH'
    if venue == 0 and raw.startswith(('000', '001', '002', '003', '300', '301', '302')):
        return raw + '.SZ'
    raise ValueError(f'Not a supported A-share security: code={raw}, venue={venue}')


def fetch_universe():
    """Commit only a fully paginated, deduplicated response; no hot-pool fallback."""
    securities, total, page = {}, None, 1
    while True:
        response = requests.get('https://82.push2.eastmoney.com/api/qt/clist/get', params={
            'pn': page, 'pz': 100, 'po': 1, 'np': 1, 'fid': 'f12', 'fltt': 2, 'invt': 2,
            'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
            'fs': 'm:0 t:6,m:0 t:80,m:1 t:2,m:1 t:23,m:0 t:81 s:2048',
            'fields': 'f12,f13,f14',
        }, timeout=8)
        response.raise_for_status()
        payload = response.json()
        data = payload.get('data')
        if payload.get('rc') != 0 or not isinstance(data, dict):
            raise ValueError('A-share universe unavailable')
        reported = data.get('total')
        if not isinstance(reported, int) or not 1000 <= reported <= 15000:
            raise ValueError('Implausible A-share universe size')
        if total is not None and reported != total:
            raise ValueError('Universe changed while paginating; retry later')
        total = reported
        rows = data.get('diff')
        rows = list(rows.values()) if isinstance(rows, dict) else rows
        if not isinstance(rows, list) or not rows:
            raise ValueError('Missing universe page')
        prior = len(securities)
        for row in rows:
            code = a_share_code(row['f12'], row['f13'])
            name = row.get('f14')
            if not isinstance(name, str) or not name:
                raise ValueError('Missing security name')
            securities[code] = {'name': name, 'board': board(code)}
        if len(securities) == total:
            return {'source': 'eastmoney_a_share_list', 'total': total, 'securities': securities}
        if len(securities) > total or len(securities) == prior or page >= 150:
            raise ValueError('Incomplete or duplicate universe pages')
        page += 1


def fetch_cohort(day):
    response = requests.get('https://push2ex.eastmoney.com/getTopicZTPool', params={
        'ut': '7eea3edcaed734bea9cbfc24409ed989', 'dpt': 'wz.ztzt', 'Pageindex': 0,
        'pagesize': 1000, 'sort': 'fbt:asc', 'date': day.replace('-', ''),
    }, timeout=8)
    response.raise_for_status()
    payload = response.json()
    data = payload.get('data')
    if payload.get('rc') != 0 or not isinstance(data, dict) or str(data.get('qdate')) != day.replace('-', ''):
        raise ValueError('Prior limit-up pool has wrong date or is unavailable')
    rows = data.get('pool')
    if not isinstance(rows, list) or not rows or len(rows) >= 1000:
        raise ValueError('Empty or possibly truncated prior limit-up pool')
    members = {}
    for row in rows:
        raw = row.get('c')
        code = a_share_code(raw, 1 if raw.startswith(('6',)) else 0)
        height = row.get('lbc')
        if not isinstance(height, int) or height < 1:
            raise ValueError('Missing consecutive-board height')
        members[code] = {'height': height, 'name': row.get('n', ''),
                         'first_limit_time': row.get('fbt'), 'last_limit_time': row.get('lbt'),
                         'open_count': row.get('zbc')}
    if len(members) != len(rows):
        raise ValueError('Duplicate cohort members')
    return {'day': day, 'source': 'eastmoney_final_daily_limit_up_pool', 'members': members}


def metrics(records):
    changes = [(r['tick']['lastPrice'] / r['tick']['lastClose'] - 1) * 100 for r in records.values()]
    up = sum(abs(r['tick']['lastPrice'] - r['info']['limit_up_price']) < .005 for r in records.values())
    down = sum(abs(r['tick']['lastPrice'] - r['info']['limit_down_price']) < .005 for r in records.values())
    touched = sum(r['tick']['high'] >= r['info']['limit_up_price'] - .005 for r in records.values())
    return {'samples': len(changes), 'median_change_pct': statistics.median(changes) if changes else None,
            'advancing_ratio': sum(x > 0 for x in changes) / len(changes) if changes else None,
            'limit_up': up, 'limit_down': down, 'touched_limit_up': touched,
            'opened_ratio': (touched - up) / touched if touched else None,
            'amount': sum(r['tick']['amount'] for r in records.values())}


def analyze(now, universe, records, cohort=None, max_age=180, min_coverage=.9):
    expected = universe['securities']
    fresh = {}
    for code, row in records.items():
        if code not in expected:
            continue
        tick = row['tick']
        quoted = datetime.fromtimestamp(tick['time'] / 1000, SHANGHAI)
        if quoted.date() == now.date() and 0 <= (now - quoted).total_seconds() <= max_age:
            fresh[code] = row
    coverage = len(fresh) / len(expected) if expected else 0
    # Risk-warning securities remain in coverage, but not the regular sentiment sample.
    regular = {c: r for c, r in fresh.items() if not any(tag in r['info']['name'].upper() for tag in ('ST', '退', 'PT'))}
    groups = {}
    for group in ('main', 'chinext', 'star', 'beijing'):
        codes = [c for c in expected if board(c) == group]
        sample = {c: regular[c] for c in codes if c in regular}
        groups[group] = dict(metrics(sample), expected=len(codes),
                             coverage=sum(c in fresh for c in codes) / len(codes) if codes else None)
    cohort_stats = None
    if cohort:
        members = cohort['members']
        observed = {c: regular[c] for c in members if c in regular}
        cohort_stats = dict(metrics(observed), day=cohort['day'], expected=len(members),
                            coverage=len(observed) / len(members) if members else 0,
                            low_open_ratio=sum(r['tick']['open'] < r['tick']['lastClose'] for r in observed.values()) / len(observed) if observed else None,
                            severe_loss_ratio=sum(r['tick']['lastPrice'] / r['tick']['lastClose'] <= .95 for r in observed.values()) / len(observed) if observed else None)
        ladder = []
        cohort_stats['unknown_height_count'] = sum(v.get('height') is None for v in members.values())
        cohort_stats['source'] = cohort['source'] if 'source' in cohort else 'unknown'
        cohort_stats['finalized'] = cohort.get('finalized', True)
        for height in sorted({v['height'] for v in members.values() if isinstance(v.get('height'), int)}):
            fixed = [c for c in members if members[c]['height'] == height]
            present = [c for c in fixed if c in observed]
            promoted = [c for c in present if abs(observed[c]['tick']['lastPrice'] - observed[c]['info']['limit_up_price']) < .005]
            ladder.append({'height': height, 'expected': len(fixed), 'observed': len(present),
                           'promoted_now': len(promoted), 'promotion_ratio_observed': len(promoted) / len(present) if present else None})
        cohort_stats['ladder'] = ladder
    ready = (coverage >= min_coverage and all(g['coverage'] is None or g['coverage'] >= min_coverage for g in groups.values())
             and cohort_stats is not None and cohort_stats['coverage'] >= min_coverage
             and cohort_stats['finalized'])
    return {'timestamp': now.isoformat(), 'scope': 'all_a_share', 'source': universe['source'],
            'expected': len(expected), 'fresh': len(fresh), 'coverage': coverage,
            'excluded_risk_names': len(fresh) - len(regular), 'boards': groups,
            'breadth': metrics(regular), 'prior_limit_up': cohort_stats, 'data_ready': ready,
            'state': '待积累趋势' if ready else '数据不足',
            'reason': ('需连续快照，不凭单个时点判断主升' if ready else
                       '昨日仅有旧表代码，未确认完整收盘快照；可看价格表现，连板高度缺失' if cohort_stats and not cohort_stats['finalized'] else
                       '证券覆盖或前一交易日涨停样本不足'),
            'rule_version': 'sentiment-v1', 'not_prediction': True}


def report():
    with journal._lock:
        db = connect()
        try:
            rows = [json.loads(row[0]) for row in db.execute('SELECT payload FROM sentiment_snapshots ORDER BY timestamp DESC LIMIT 60')]
            return {'snapshots': rows, 'scope': 'all_a_share', 'notice': '规则观察，不预测明日资金；停牌或无涨跌幅数据计为缺失，不冒充有效覆盖'}
        finally:
            db.close()


class MarketSentimentMonitor:
    def __init__(self, config=None):
        self.config = config or {}
        self.provider = PublicQuoteProvider(timeout_seconds=5)
        self.interval = max(120, float(self.config.get('interval_seconds', 120)))
        self._stop = threading.Event()
        self._thread = None
        self.status = {'running': False, 'reason': '尚未启动', 'last_attempt': None, 'last_success': None}
        self._day = None
        self._universe = None
        self._cohort = None
        from curs.relay import RelayMonitor
        self.relay = RelayMonitor(self.config.get('relay', {}))

    def prepare(self, now):
        day = now.date().isoformat()
        universe = stored('market_universe', day) or fetch_universe()
        persist('market_universe', day, universe)
        bars = get_stock_kline_data('000001.SH', count=30)
        prior_days = [d for d in (bars or {}).get('dates', []) if d < day]
        self._cohort = None
        if prior_days:
            previous = max(prior_days)
            if (now.date() - datetime.fromisoformat(previous).date()).days <= 10:
                try:
                    from curs.database import get_db_manager
                    self._cohort = get_db_manager().get_zt_snapshot(previous) or stored('market_cohorts', previous) or fetch_cohort(previous)
                    if self._cohort.get('finalized', True):
                        persist('market_cohorts', previous, self._cohort, immutable=True)
                except Exception:
                    logger.exception('Prior-session limit-up cohort unavailable')
        self._universe, self._day = universe, now.date()

    def poll_once(self, now=None):
        now = now or datetime.now(SHANGHAI)
        if now.weekday() >= 5 or not ('09:30' <= now.strftime('%H:%M') <= '11:30' or '13:00' <= now.strftime('%H:%M') <= '15:05'):
            self.status['reason'] = '非交易采集时段'
            return
        self.status.update(last_attempt=now.isoformat(), reason='采集全市场快照')
        if self._day != now.date() or self._cohort is None:
            self.prepare(now)
        rows = self.provider.get_quotes(list(self._universe['securities']))
        finished = datetime.now(SHANGHAI)
        snapshot = analyze(finished, self._universe, rows, self._cohort,
                           max_age=float(self.config.get('max_age_seconds', 180)),
                           min_coverage=float(self.config.get('min_coverage', .9)))
        recent = report()['snapshots'][:2]
        if (snapshot['data_ready'] and len(recent) == 2
                and all(s['data_ready'] and s['timestamp'][:10] == finished.date().isoformat()
                        and 0 < (finished - datetime.fromisoformat(s['timestamp'])).total_seconds() <= 600 for s in recent)):
            current = snapshot['breadth']['median_change_pct']
            previous = recent[0]['breadth']['median_change_pct']
            earlier = recent[1]['breadth']['median_change_pct']
            premium = snapshot['prior_limit_up']['median_change_pct']
            negative = snapshot['prior_limit_up']['severe_loss_ratio']
            if snapshot['breadth']['advancing_ratio'] >= .6 and current > previous > earlier and premium > 0:
                snapshot.update(state='扩散观察', reason='连续三次广度改善，昨日涨停样本仍有正溢价；不等同情绪主升确认')
            elif current < previous < earlier and premium < 0 and negative >= .2:
                snapshot.update(state='退潮风险观察', reason='连续三次广度恶化，昨日涨停样本负溢价且大跌比例较高')
            else:
                snapshot.update(state='分歧/中性观察', reason='广度与短线赚钱效应未形成一致方向')
        persist('sentiment_snapshots', snapshot['timestamp'], snapshot)
        try:
            self.relay.scan(finished, rows, self._cohort, snapshot)
        except Exception:
            logger.exception('Relay shadow assessment failed; sentiment collection remains independent')
        self.status.update(reason=snapshot['reason'], data_ready=snapshot['data_ready'])
        if snapshot['data_ready']:
            self.status['last_success'] = snapshot['timestamp']

    def _run(self):
        while not self._stop.is_set():
            try:
                self.poll_once()
            except Exception:
                self.status.update(reason='全市场采集失败，无法判断', data_ready=False)
                logger.exception('Market sentiment collection failed; retry later')
            self._stop.wait(self.interval)

    def start(self):
        if not self.config.get('enabled', True):
            self.status['reason'] = '已禁用'
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name='MarketSentiment', daemon=True)
        self._thread.start()
        self.status['running'] = True

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        self.status['running'] = bool(self._thread and self._thread.is_alive())

    def get_status(self):
        result = dict(self.status)
        now = datetime.now(SHANGHAI)
        active = now.weekday() < 5 and ('09:30' <= now.strftime('%H:%M') <= '11:30' or '13:00' <= now.strftime('%H:%M') <= '15:05')
        result['session'] = 'active' if active else 'outside_session'
        last = result.get('last_success')
        if not active or not last or (now - datetime.fromisoformat(last)).total_seconds() > 300:
            result['data_ready'] = False
        return result
