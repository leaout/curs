# coding: utf-8
"""Shadow-only continuation assessment using frozen cohorts and sampled quotes."""

import json
from datetime import datetime

from curs import signal_recorder as journal
from curs.broker.public_quote import SHANGHAI


class RelayMonitor:
    def __init__(self, config=None):
        self.config = config or {}
        self.day = None
        self.states = {}

    def evaluate(self, now, records, cohort, snapshot):
        if self.day != now.date():
            self.day, self.states = now.date(), {}
        if not cohort or cohort.get('finalized', True) is not True:
            self.states.clear()
            return []
        prior = snapshot.get('prior_limit_up') or {}
        if cohort.get('day') != prior.get('day') or cohort['day'] >= now.date().isoformat():
            self.states.clear()
            return []
        results = []
        groups = self.config.get('groups', {})
        for code, member in cohort['members'].items():
            height = member.get('height')
            if not isinstance(height, int) or isinstance(height, bool) or height < 1:
                continue
            row = records.get(code)
            reasons, evidence = [], {'cohort_day':cohort['day'], 'prior_height':height}
            if not snapshot.get('data_ready'):
                reasons.append('全市场或昨日样本覆盖不足')
            if snapshot.get('state') == '退潮风险观察' or (
                    prior.get('median_change_pct') is not None and prior['median_change_pct'] < 0
                    and (prior.get('severe_loss_ratio') or 0) >= .2):
                reasons.append('昨日涨停负反馈，环境否决')
            fresh = False
            if row:
                tick, info = row['tick'], row['info']
                quoted = datetime.fromtimestamp(tick['time']/1000, SHANGHAI)
                fresh = quoted.date() == now.date() and 0 <= (now-quoted).total_seconds() <= 180
            if not fresh:
                self.states.pop(code, None)
                reasons.append('个股行情缺失或过期')
            else:
                upper, price, close = info['limit_up_price'], tick['lastPrice'], tick['lastClose']
                if 'ST' in info.get('name', '').upper() or '退' in info.get('name', '') or not .095 <= upper/close-1 <= .105:
                    reasons.append('第一版仅支持非风险警示10%涨停证券')
                state = self.states.get(code)
                gap = state is None or not 0 <= tick['time']/1000-state['last'] <= 180 or tick['amount'] < state['amount']
                sealed = abs(price-upper) < .005
                if gap:
                    state = {'last':tick['time']/1000, 'sealed':sealed, 'start':tick['time']/1000,
                             'samples':1, 'breaks':0, 'initial_amount':tick['amount'], 'amount':tick['amount']}
                elif tick['time']/1000 > state['last']:
                    if state['sealed'] and not sealed:
                        state['breaks'] += 1
                    if not sealed or not state['sealed']:
                        state.update(start=tick['time']/1000, samples=0, initial_amount=tick['amount'])
                    state.update(last=tick['time']/1000, sealed=sealed, amount=tick['amount'], samples=state['samples']+1)
                self.states[code] = state
                elapsed = state['last']-state['start']
                evidence.update(observed_breaks=state['breaks'], sampled_seal_seconds=elapsed,
                                samples=state['samples'], quote_time=quoted.isoformat(),
                                opening_gap_pct=round((tick['open']/close-1)*100, 2))
                if not sealed or elapsed < 240 or state['samples'] < 3 or tick['amount'] <= state['initial_amount']:
                    reasons.append('等待至少三次有效快照、封板持续与新增成交')
                if state['breaks'] >= 2:
                    reasons.append('已观察到多次开板')
                if tick['open'] >= upper-.005 and tick.get('low', price) >= upper-.005:
                    reasons.append('一字状态，无法确认可成交性')
                group = next((name for name, codes in groups.items() if code in codes), None)
                peers = []
                if group:
                    for other in groups[group]:
                        peer = records.get(other)
                        if other == code or not peer:
                            continue
                        pt = peer['tick']
                        qt = datetime.fromtimestamp(pt['time']/1000, SHANGHAI)
                        if qt.date() == now.date() and 0 <= (now-qt).total_seconds() <= 180 and pt['lastPrice']/pt['lastClose'] >= 1.03:
                            peers.append(other)
                evidence.update(theme=group, strong_peers=peers)
                if not group or len(peers) < 2:
                    reasons.append('明确题材共振不足，不以全观察池代替题材')
            if reasons:
                # Invalidate seal continuity across unhealthy market coverage.
                if not snapshot.get('data_ready'):
                    self.states.pop(code, None)
            results.append({'timestamp':now.isoformat(), 'stock_code':code, 'stock_name':member.get('name'),
                            'stage':'一进二' if height == 1 else '二进三' if height == 2 else '高位接力',
                            'status':'待观察' if reasons else '影子条件通过', 'reasons':reasons,
                            'evidence':evidence, 'mode':'shadow', 'rule_version':'relay-v1'})
        return results

    def scan(self, now, records, cohort, snapshot):
        if not self.config.get('enabled', True):
            return
        rows = self.evaluate(now, records, cohort, snapshot)
        if self.config.get('kol_context', {}).get('enabled', True) and rows:
            try:
                from curs.kol_intent.relay_context import contexts
                opinions = contexts([r['stock_code'] for r in rows], now,
                                    self.config.get('kol_context', {}).get('lookback_hours', 48))
                for row in rows:
                    opinion = opinions[row['stock_code']]
                    row['kol_context'] = opinion
                    row['kol_shadow_status'] = ('分歧待复核' if row['status'] == '影子条件通过'
                                                and opinion['assessment'] == '明确分歧' else row['status'])
            except Exception:
                import logging
                logging.getLogger(__name__).exception('KOL context unavailable; baseline relay remains independent')
                for row in rows:
                    row['kol_context'] = {'assessment':'数据不可用', 'evidence':[], 'mode':'shadow'}
        with journal._lock:
            db = journal._connect()
            try:
                db.execute('CREATE TABLE IF NOT EXISTS relay_observations (timestamp TEXT, code TEXT, payload TEXT, PRIMARY KEY(timestamp,code))')
                db.executemany('INSERT OR IGNORE INTO relay_observations VALUES (?,?,?)',
                               [(r['timestamp'], r['stock_code'], json.dumps(r, ensure_ascii=False)) for r in rows])
                db.commit()
            finally:
                db.close()


def report():
    with journal._lock:
        db = journal._connect()
        try:
            exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='relay_observations'").fetchone()
            rows = db.execute('SELECT payload FROM relay_observations WHERE timestamp=(SELECT MAX(timestamp) FROM relay_observations) ORDER BY code').fetchall() if exists else []
            return {'observations':[json.loads(r[0]) for r in rows], 'mode':'shadow',
                    'notice':'按记录时间查看，非当前有效建议；采样可能漏掉开板，不确认连续封单或成交，不修改原策略'}
        finally:
            db.close()
