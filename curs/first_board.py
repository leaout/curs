# coding: utf-8
"""Conservative snapshot confirmation; signals never imply executable fills."""

import json
import logging
from datetime import datetime
from types import SimpleNamespace

from curs import signal_recorder as journal

logger = logging.getLogger(__name__)


def candidates():
    with journal._lock:
        db = journal._connect()
        try:
            db.execute('''CREATE TABLE IF NOT EXISTS first_board_candidates (
                day TEXT, code TEXT, updated TEXT, state TEXT, reason TEXT, evidence TEXT,
                PRIMARY KEY(day, code))''')
            rows = [dict(row) for row in db.execute(
                'SELECT * FROM first_board_candidates ORDER BY updated DESC LIMIT 100')]
            confirmed = {(r[0], r[1]) for r in db.execute("SELECT trade_date,stock_code FROM signals WHERE strategy_name='first_board_confirmation'")}
            for row in rows:
                if (row['day'], row['code']) in confirmed:
                    row.update(state='confirmed', reason='已记录确认信号；后续价格变动见信号观察')
            return rows
        finally:
            db.close()


class FirstBoardMonitor:
    def __init__(self, config=None, bars=None):
        from curs.broker.public_quote import get_stock_kline_data
        self.config = config or {}
        self.bars = bars or get_stock_kline_data
        self.day = None
        self.states = {}
        self.eligibility = {}
        self.duration = max(30, float(self.config.get('confirm_seconds', 60)))
        self.max_gap = max(5, float(self.config.get('max_gap_seconds', 15)))
        self.groups = self.config.get('groups', {})
        self._retry_after = {}
        self._confirmed = set()

    def save(self, now, code, state, reason, evidence=None):
        with journal._lock:
            db = journal._connect()
            try:
                db.execute('''CREATE TABLE IF NOT EXISTS first_board_candidates (
                    day TEXT, code TEXT, updated TEXT, state TEXT, reason TEXT, evidence TEXT,
                    PRIMARY KEY(day, code))''')
                db.execute('INSERT OR REPLACE INTO first_board_candidates VALUES (?, ?, ?, ?, ?, ?)',
                           (now.date().isoformat(), code, now.isoformat(), state, reason,
                            json.dumps(evidence or {}, ensure_ascii=False)))
                db.commit()
            finally:
                db.close()

    def check_history(self, code, tick, now):
        bars = self.bars(code, count=12)
        rows = [(date, candle) for date, candle in zip((bars or {}).get('dates', []), (bars or {}).get('kline_data', []))
                if date < now.date().isoformat()]
        if len(rows) < 6:
            return False, '日线不足，排除新股或缺失数据'
        previous, latest = rows[-2], rows[-1]
        if not 0 < (now.date() - datetime.fromisoformat(latest[0]).date()).days <= 10:
            return False, '日线过期，无法确认首板'
        if abs(latest[1][1] / tick['lastClose'] - 1) > .015:
            return False, '日线与昨收不一致，暂停确认'
        if latest[1][1] / previous[1][1] - 1 >= .095:
            return False, '前一交易日疑似涨停，不属于首板'
        return True, '近期日线检查通过'

    def scan(self, now, records, ready):
        if not self.config.get('enabled', True):
            return
        if self.day != now.date():
            self.day, self.states, self.eligibility = now.date(), {}, {}
            self._retry_after.clear()
            with journal._lock:
                db = journal._connect()
                try:
                    self._confirmed = {r[0] for r in db.execute("SELECT stock_code FROM signals WHERE trade_date=? AND strategy_name='first_board_confirmation'", (now.date().isoformat(),))}
                finally:
                    db.close()
        for code in list(self.states):
            if code not in records and code not in self._confirmed:
                self.states.pop(code)
                self.save(now, code, 'paused', '个股行情缺失，持续确认重新计时')
        if not ready:
            for code in list(self.states):
                if code not in self._confirmed:
                    self.save(now, code, 'paused', '行情覆盖不足，持续确认重新计时')
            self.states.clear()
            return
        history_budget = 1
        for code, row in records.items():
            if code in self._confirmed:
                continue
            tick, info = row['tick'], row['info']
            upper, price = info['limit_up_price'], tick['lastPrice']
            if not code.startswith(('600', '601', '603', '605', '000', '001', '002', '003')):
                continue
            name = info.get('name', '').upper()
            if 'ST' in name or '退' in name or not .095 <= upper / tick['lastClose'] - 1 <= .105:
                continue
            if price < upper * .99:
                if code in self.states:
                    self.states.pop(code)
                    self.save(now, code, 'abandoned', '价格离开临板区域')
                continue
            if code not in self.eligibility:
                if now.timestamp() < self._retry_after.get(code, 0):
                    continue
                if not history_budget:
                    continue
                history_budget -= 1
                try:
                    self.eligibility[code] = self.check_history(code, tick, now)
                except Exception:
                    self._retry_after[code] = now.timestamp() + 60
                    logger.exception('First-board daily history unavailable: %s', code)
                    self.save(now, code, 'paused', '日线请求失败，稍后重试')
                    continue
            eligible, reason = self.eligibility[code]
            if not eligible:
                self.save(now, code, 'excluded', reason)
                continue
            group = next((label for label, members in self.groups.items() if code in members), None)
            peers = self.groups[group] if group else list(records)
            strong = sum(c != code and c in records and records[c]['tick']['lastPrice'] / records[c]['tick']['lastClose'] >= 1.03 for c in peers)
            scope = group or '观察池（非题材板块）'
            evidence = {'scope': scope, 'strong_peers': strong, 'confirm_seconds': self.duration}
            quoted = tick['time'] / 1000
            state = self.states.get(code)
            if state and state.get('signaled'):
                continue
            sealed = abs(price - upper) < .005
            if not sealed or strong < int(self.config.get('min_strong_peers', 3)):
                self.states.pop(code, None)
                self.save(now, code, 'candidate', '等待封板与同步走强确认', evidence)
                continue
            if not state or quoted - state['last'] > self.max_gap or tick['amount'] < state['amount']:
                state = {'start': quoted, 'last': quoted, 'amount': tick['amount'], 'initial_amount': tick['amount'], 'samples': 1}
                self.states[code] = state
            elif quoted > state['last']:
                state.update(last=quoted, amount=tick['amount'], samples=state['samples'] + 1)
            elapsed = quoted - state['start']
            evidence.update(elapsed_seconds=elapsed, samples=state['samples'], amount_increase=tick['amount'] - state['initial_amount'])
            if elapsed >= self.duration and state['samples'] >= 3 and tick['amount'] > state['initial_amount']:
                context = SimpleNamespace(current_time=now)
                if journal.record_signal(context, 'first_board_confirmation', code, price, 100):
                    self._confirmed.add(code)
                    state['signaled'] = True
                    self.save(now, code, 'confirmed', '封板持续、成交额增加、同步走强确认；未确认成交', evidence)
            else:
                self.save(now, code, 'confirming', '持续确认中', evidence)
