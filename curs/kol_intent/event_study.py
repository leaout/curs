# coding: utf-8
"""Market-adjusted event windows on the supplied trading calendar."""

import numpy as np
import pandas as pd


def event_study(events: pd.DataFrame, prices: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compute raw (not direction-signed) CAR[-1,+5]; incomplete CAR is null.

    Non-session events map to the next supplied session. Market returns average
    available ticker close-to-close returns without forward filling. Windows
    retain missing values and count their observed samples in the mean curve.
    """
    closes = prices.pivot(index='timestamp', columns='ticker', values='close').sort_index()
    returns = closes.pct_change(fill_method=None)
    abnormal = returns.sub(returns.mean(axis=1), axis=0)
    calendar = closes.index
    details, windows = [], []
    for event in events.to_dict('records'):
        center = calendar.searchsorted(event['timestamp'].normalize())
        values = []
        for offset in range(-1, 6):
            position = center + offset
            value = abnormal.iloc[position][event['ticker']] if 0 <= position < len(calendar) else np.nan
            values.append(value)
        cumulative = np.cumsum(values)
        complete = bool(np.isfinite(values).all())
        details.append(dict(event_id=event['event_id'], ticker=event['ticker'],
                            timestamp=event['timestamp'], direction=event['direction'],
                            event_date=calendar[center] if center < len(calendar) else pd.NaT,
                            car=float(sum(values)) if complete else np.nan,
                            complete_window=complete, observed_days=int(np.isfinite(values).sum())))
        windows.append(cumulative)
    matrix = np.array(windows, dtype=float).reshape(-1, 7)
    counts = np.isfinite(matrix).sum(axis=0)
    means = np.divide(np.nansum(matrix, axis=0), counts, out=np.full(7, np.nan), where=counts > 0)
    curve = pd.DataFrame({'relative_day': range(-1, 6), 'mean_car': means, 'event_count': counts})
    columns = ['event_id', 'ticker', 'timestamp', 'direction', 'event_date', 'car', 'complete_window', 'observed_days']
    return pd.DataFrame(details, columns=columns), curve
