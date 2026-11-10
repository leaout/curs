# coding: utf-8
"""Read-only opportunity grouping; never merges or changes underlying executions."""

from datetime import datetime
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo('Asia/Shanghai')


def signal_time(row):
    value = row['timestamp']
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value.replace(tzinfo=SHANGHAI) if value.tzinfo is None else value.astimezone(SHANGHAI)


def group_opportunities(signals):
    groups = {}
    for row in signals:
        day = signal_time(row).date().isoformat()
        key = (day, row['stock_code'], row['signal_type'])
        groups.setdefault(key, []).append(row)
    result = []
    for (day, code, direction), members in groups.items():
        members = sorted(members, key=lambda row: (signal_time(row), str(row.get('order_id') or row.get('id') or '')))
        first = dict(members[0])
        strategies = sorted({row['strategy_name'] for row in members})
        statuses = {row.get('status', 'SIGNAL_ONLY') or 'UNKNOWN' for row in members}
        first.update(opportunity_id=f'{day}:{code}:{direction}', trade_date=day,
                     strategies=strategies, strategy_count=len(strategies), trigger_count=len(members),
                     first_trigger=signal_time(members[0]).isoformat(), last_trigger=signal_time(members[-1]).isoformat(),
                     reference_rule='最早触发的参考价与其后续观察；不代表成交，不累加数量',
                     signals=[dict(row, timestamp=signal_time(row).isoformat()) for row in members],
                     status=next(iter(statuses)) if len(statuses) == 1 else 'MIXED',
                     mirror_pending=any(row.get('mirror_pending', False) for row in members))
        result.append(first)
    return sorted(result, key=lambda row: row['last_trigger'], reverse=True)
