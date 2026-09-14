# coding: utf-8
"""只处理闭合 K 线的轻量增量指标引擎。"""

from collections import defaultdict, deque
from decimal import Decimal
from typing import Deque, Dict, Tuple

from curs.domain.models import Bar


class IndicatorEngine:
    def __init__(self, history_size: int = 240):
        if history_size < 20:
            raise ValueError('history_size must be at least 20')
        self._history_size = history_size
        self._bars: Dict[Tuple[str, str], Deque[Bar]] = defaultdict(
            lambda: deque(maxlen=self._history_size)
        )

    def update(self, bar: Bar) -> Dict[str, Decimal]:
        if not bar.is_closed:
            raise ValueError('indicators can only consume closed bars')
        key = (str(bar.instrument), bar.timeframe)
        history = self._bars[key]
        previous = history[-1] if history else None
        history.append(bar)

        features: Dict[str, Decimal] = {
            'open': bar.open,
            'high': bar.high,
            'low': bar.low,
            'close': bar.close,
            'volume': bar.volume,
        }
        if previous and previous.close:
            features['change_pct_1'] = (bar.close / previous.close) - Decimal('1')

        closes = [item.close for item in history]
        volumes = [item.volume for item in history]
        for period in (5, 10, 20, 60):
            if len(history) >= period:
                features[f'ma_{period}'] = sum(closes[-period:]) / Decimal(period)
                features[f'volume_ma_{period}'] = sum(volumes[-period:]) / Decimal(period)

        if len(history) >= 2:
            lookback = list(history)[:-1][-20:]
            features['recent_high_20'] = max(item.high for item in lookback)
            features['recent_low_20'] = min(item.low for item in lookback)
        if len(history) >= 20 and features['volume_ma_20']:
            features['volume_ratio_20'] = bar.volume / features['volume_ma_20']
        return features
