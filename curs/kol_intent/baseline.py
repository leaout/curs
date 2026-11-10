# coding: utf-8
"""Offline trade intervals and equal-weight open-rebalanced portfolio accounting."""

import numpy as np
import pandas as pd

TRADE_COLUMNS = ['event_id', 'ticker', 'entry_date', 'exit_date', 'entry_price',
                 'exit_price', 'return', 'reason', 'supported_long']


def generate_trades(events: pd.DataFrame, prices: pd.DataFrame,
                    holding_days: int = 5) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build long-only intervals; entry day is day one, exit at day six open.

    Trading dates are the union of supplied daily bars. Missing entry opens skip
    the signal; missing exit opens defer liquidation. Unclosed trades remain
    marked open. Simultaneous long/short signals cancel entry for that ticker.
    Returns include overnight gaps and open-to-close moves separately, with
    equal weights rebalanced at each available open and unpriced slots in cash.
    """
    if holding_days < 1:
        raise ValueError('holding_days must be positive')
    opens = prices.pivot(index='timestamp', columns='ticker', values='open').sort_index()
    closes = prices.pivot(index='timestamp', columns='ticker', values='close').reindex_like(opens)
    calendar = opens.index
    records = []
    for ticker, group in events.groupby('ticker', sort=True):
        if ticker not in opens.columns:
            continue
        group = group.sort_values(['timestamp', 'event_id']).copy()
        group['execution_index'] = group['timestamp'].map(lambda stamp: calendar.searchsorted(stamp.normalize(), side='right'))
        blocked_until = -1
        for index, same_day in group.groupby('execution_index', sort=True):
            if index >= len(calendar) or index < blocked_until:
                continue
            if 'short' in set(same_day['direction']):
                continue
            candidates = same_day[same_day['direction'] == 'long']
            if candidates.empty or pd.isna(opens.iloc[index][ticker]):
                continue
            event = candidates.iloc[0]
            planned_exit = index + holding_days
            shorts = group[(group['direction'] == 'short') & (group['execution_index'] > index)]
            short_exit = int(shorts['execution_index'].min()) if not shorts.empty else len(calendar)
            target = min(planned_exit, short_exit)
            reason = 'short' if short_exit <= planned_exit and short_exit < len(calendar) else 'holding_period'
            available = np.flatnonzero(opens[ticker].notna().to_numpy() & (np.arange(len(calendar)) >= target))
            exit_index = int(available[0]) if len(available) else len(calendar)
            entry_price = float(opens.iloc[index][ticker])
            exit_price = float(opens.iloc[exit_index][ticker]) if exit_index < len(calendar) else None
            records.append(dict(event_id=event['event_id'], ticker=ticker, entry_date=calendar[index],
                                exit_date=calendar[exit_index] if exit_price is not None else pd.NaT,
                                entry_price=entry_price, exit_price=exit_price,
                                return_value=exit_price / entry_price - 1 if exit_price is not None else None,
                                reason=reason if exit_price is not None else 'open_at_end',
                                supported_long=bool(event['supported_long'])))
            blocked_until = exit_index
    trades = pd.DataFrame(records).rename(columns={'return_value': 'return'}).reindex(columns=TRADE_COLUMNS)
    active = pd.DataFrame(False, index=calendar, columns=opens.columns)
    for trade in trades.to_dict('records'):
        active.loc[(calendar >= trade['entry_date']) &
                   (True if pd.isna(trade['exit_date']) else calendar < trade['exit_date']), trade['ticker']] = True
    previous_close = closes.ffill().shift(1)
    # A stale bar retains its last valuation; it does not earn an invented return.
    marks_at_open = opens.where(opens.notna(), previous_close)
    marks_at_close = closes.where(closes.notna(), previous_close)
    gross_overnight = marks_at_open.div(previous_close).fillna(1.0)
    gross_intraday = marks_at_close.div(marks_at_open).fillna(1.0)
    weights = active.astype(float).div(active.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
    # Missing opens prevent rebalancing that day. Carry drifted holdings instead.
    held = pd.Series(0.0, index=opens.columns)
    daily = []
    for day in calendar:
        overnight_assets = held * gross_overnight.loc[day]
        overnight_value = 1.0 - held.sum() + overnight_assets.sum()
        desired = weights.loc[day].copy()
        missing_held = opens.loc[day].isna() & (held > 0)
        if missing_held.any():
            desired.loc[missing_held] = overnight_assets.loc[missing_held] / overnight_value
            tradable = ~missing_held
            tradable_total = desired.loc[tradable].sum()
            if tradable_total > 0:
                desired.loc[tradable] *= max(0.0, 1.0 - desired.loc[missing_held].sum()) / tradable_total
        desired.loc[opens.loc[day].isna() & ~missing_held] = 0.0
        end_assets = desired * gross_intraday.loc[day]
        intraday_value = 1.0 - desired.sum() + end_assets.sum()
        held = end_assets / intraday_value
        daily.append(dict(timestamp=day, daily_return=float(overnight_value * intraday_value - 1),
                          exposure=float(desired.sum())))
    return trades, pd.DataFrame(daily)
