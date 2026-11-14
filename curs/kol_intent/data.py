# coding: utf-8
"""Validate research inputs and adapt the existing public daily-bar API."""

import re

import numpy as np
import pandas as pd


def ticker_code(value: str) -> str:
    """Normalize supported A-share aliases; preserve other explicit symbols."""
    value = str(value).strip().upper().replace('.XSHG', '.SH').replace('.XSHE', '.SZ')
    if re.fullmatch(r'(\d{6}|\d{6}\.(SH|SZ|BJ)|(SH|SZ|BJ)\d{6}|STOCK_(SH|SZ|BJ)_\d{6})', value):
        from curs.broker.public_quote import normalize_code
        return normalize_code(value)
    if not value or value == 'NAN':
        raise ValueError('Empty ticker')
    return value


def local_timestamp(value: object) -> pd.Timestamp:
    """Parse ISO or YYYYMMDD timestamps into Asia/Shanghai time."""
    if pd.isna(value):
        raise ValueError('Missing timestamp')
    stamp = pd.Timestamp(str(value))
    return stamp.tz_localize('Asia/Shanghai') if stamp.tzinfo is None else stamp.tz_convert('Asia/Shanghai')


def prepare_prices(prices: pd.DataFrame) -> pd.DataFrame:
    """Return unique, positive daily open/close prices sorted by date/ticker."""
    frame = prices.rename(columns={'date': 'timestamp', 'last': 'close'}).copy()
    required = {'timestamp', 'ticker', 'open', 'close'}
    if not required.issubset(frame.columns):
        raise ValueError(f'Prices require {sorted(required)}')
    frame['ticker'] = frame['ticker'].map(ticker_code)
    frame['timestamp'] = frame['timestamp'].map(local_timestamp).dt.normalize()
    for field in ('open', 'close'):
        frame[field] = pd.to_numeric(frame[field], errors='raise')
        if not (np.isfinite(frame[field]) & (frame[field] > 0)).all():
            raise ValueError(f'Invalid {field} price')
    if frame.empty or frame.duplicated(['timestamp', 'ticker']).any():
        raise ValueError('Prices must be nonempty with unique date/ticker rows')
    return frame.sort_values(['timestamp', 'ticker']).reset_index(drop=True)


def load_public_prices(tickers: list[str], count: int = 250, adjustment: str = 'qfq') -> pd.DataFrame:
    """Read daily bars only through the project's existing public interface."""
    from curs.broker.public_quote import get_stock_kline_data
    rows = []
    for ticker in tickers:
        bars = get_stock_kline_data(ticker, count=count, adjustment=adjustment)
        if bars:
            for day, candle in zip(bars['dates'], bars['kline_data']):
                rows.append(dict(timestamp=day, ticker=bars['stock_code'], open=candle[0], close=candle[1]))
    return prepare_prices(pd.DataFrame(rows))
