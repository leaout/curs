# coding: utf-8
"""Point-in-time, auditable KOL context. Never emits orders or changes risk gates."""

import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timedelta
from urllib.parse import urlsplit

from curs import signal_recorder as journal
from curs.broker.public_quote import SHANGHAI
from curs.kol_intent.extractor import rule_direction


def stamp(value):
    parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timestamp must include timezone')
    return parsed.astimezone(SHANGHAI)


def connect():
    db = journal._connect()
    db.execute('''CREATE TABLE IF NOT EXISTS kol_public_posts (
        identity TEXT PRIMARY KEY, stock_code TEXT NOT NULL, published_at TEXT NOT NULL,
        collected_at TEXT NOT NULL, payload TEXT NOT NULL)''')
    db.execute('CREATE INDEX IF NOT EXISTS kol_posts_code_time ON kol_public_posts(stock_code, collected_at)')
    return db


def classify(text):
    if re.search(r'(?:不|别|勿|未|无意|不能|不会|不再).{0,5}(?:看多|买入|加仓|看空|卖出|减仓)|\b(?:no|not|never)\b', text, re.I):
        return '否定或不确定表达', 'neutral', []
    if re.search(r'转发|转述|据说|听说|网传|转载|\b(?:repost|rumor|reportedly)\b', text, re.I):
        return '转述', 'neutral', []
    if re.search(r'昨天|昨日|上周|此前|已经|复盘|晒单|\b(?:yesterday|bought|sold|previously)\b', text, re.I):
        return '回顾', 'neutral', []
    if re.search(r'持仓|持有|仓位|\b(?:holding|position)\b', text, re.I):
        return '持仓披露', 'neutral', []
    if re.search(r'[?？]|如果|假如|一旦|计划|考虑|希望|\b(?:if|might|may|plan|consider)\b', text, re.I):
        return '条件或不确定表达', 'neutral', []
    direction, evidence = rule_direction(text)
    return ('明确方向' if direction != 'neutral' else '无明确方向', direction, evidence)


def import_csv(path, now=None):
    """Local first observation is import time, never a caller-supplied backdate."""
    now = now or datetime.now(SHANGHAI)
    now = stamp(now)
    posts = []
    with open(path, encoding='utf-8-sig', newline='') as source:
        reader = csv.DictReader(source)
        required = {'author', 'source_url', 'published_at', 'stock_code', 'text'}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError('CSV requires ' + ','.join(sorted(required)))
        for number, row in enumerate(reader, 2):
            author, code, text = (row[key].strip() for key in ('author', 'stock_code', 'text'))
            url = row['source_url'].strip()
            parts = urlsplit(url)
            published = stamp(row['published_at'])
            if not author or not text or len(text) > 10000 or not re.fullmatch(r'\d{6}\.(SH|SZ|BJ)', code):
                raise ValueError(f'Invalid author, text or explicit stock code at row {number}')
            if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password:
                raise ValueError(f'Invalid public HTTPS link at row {number}')
            if published > now:
                raise ValueError(f'Future publication at row {number}')
            normalized = ' '.join(text.split())
            # Source fragment differences cannot duplicate a post; edits become new observations.
            url = parts._replace(fragment='').geturl()
            identity = hashlib.sha256(json.dumps([author,url,code,normalized,published.isoformat()],ensure_ascii=False).encode()).hexdigest()
            kind, direction, evidence = classify(normalized)
            payload = dict(author=author, source_url=url, stock_code=code, text=normalized,
                           published_at=published.isoformat(), collected_at=now.isoformat(),
                           kind=kind, direction=direction, evidence=evidence, rule_version='kol-relay-v1')
            posts.append((identity,code,published.isoformat(),now.isoformat(),json.dumps(payload,ensure_ascii=False)))
    with journal._lock:
        db = connect()
        try:
            before = db.total_changes
            db.executemany('INSERT OR IGNORE INTO kol_public_posts VALUES (?,?,?,?,?)', posts)
            inserted = db.total_changes-before
            db.commit()
        finally:
            db.close()
    return {'inserted':inserted, 'duplicates':len(posts)-inserted, 'collected_at':now.isoformat()}


def contexts(codes, cutoff, lookback_hours=48):
    cutoff = stamp(cutoff)
    if not 0 < lookback_hours <= 168:
        raise ValueError('lookback_hours must be in (0,168]')
    since = cutoff-timedelta(hours=lookback_hours)
    result = {}
    with journal._lock:
        db = connect()
        try:
            for code in codes:
                rows = db.execute('''SELECT payload FROM kol_public_posts WHERE stock_code=?
                    AND published_at>=? AND published_at<? AND collected_at<?
                    ORDER BY published_at DESC, collected_at DESC''',
                    (code,since.isoformat(),cutoff.isoformat(),cutoff.isoformat())).fetchall()
                posts = [json.loads(row[0]) for row in rows]
                # Latest explicit opinion per author; identical copied opinions count once.
                authors, contents, used = set(), set(), []
                for post in posts:
                    if post['direction'] == 'neutral' or post['author'] in authors:
                        continue
                    authors.add(post['author'])
                    content = re.sub(r'\W+', '', post['text']).casefold()
                    if content in contents:
                        continue
                    contents.add(content)
                    used.append(post)
                directions = {p['direction'] for p in used}
                label = '明确分歧' if 'short' in directions else '明确支持' if 'long' in directions else '无有效信息'
                result[code] = {'assessment':label, 'supporting':sum(p['direction']=='long' for p in used),
                                'opposing':sum(p['direction']=='short' for p in used),
                                'eligible_posts':len(posts), 'evidence':used[:10],
                                'excluded_non_directional':sum(p['direction']=='neutral' for p in posts),
                                'cutoff':cutoff.isoformat(), 'lookback_hours':lookback_hours,
                                'rule_version':'kol-relay-v1', 'mode':'shadow',
                                'notice':'人工导入、来源与作者未独立认证；仅规则意见，不代表胜率或真实资金'}
            db.commit()
        finally:
            db.close()
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Import public KOL CSV with actual local first-seen time')
    parser.add_argument('csv_path')
    args = parser.parse_args()
    print(json.dumps(import_csv(args.csv_path), ensure_ascii=False))
