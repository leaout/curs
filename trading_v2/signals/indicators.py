# coding: utf-8
"""Pure-Python indicator calculations used by the allowlisted strategy DSL."""

from typing import Sequence

from trading_v2.domain.market import Bar

NumberSeries = list[float | None]


def field_series(bars: Sequence[Bar], name: str) -> NumberSeries:
    return [float(getattr(bar, name)) for bar in bars]


def sma(values: Sequence[float], period: int) -> NumberSeries:
    _validate_period(period)
    output: NumberSeries = [None] * len(values)
    for index in range(period - 1, len(values)):
        output[index] = sum(values[index - period + 1:index + 1]) / period
    return output


def ema(values: Sequence[float], period: int) -> NumberSeries:
    _validate_period(period)
    if len(values) < period:
        return [None] * len(values)
    output: NumberSeries = [None] * len(values)
    seed = sum(values[:period]) / period
    output[period - 1] = seed
    multiplier = 2 / (period + 1)
    previous = seed
    for index in range(period, len(values)):
        previous = (values[index] - previous) * multiplier + previous
        output[index] = previous
    return output


def rsi(values: Sequence[float], period: int) -> NumberSeries:
    _validate_period(period)
    output: NumberSeries = [None] * len(values)
    if len(values) <= period:
        return output
    gains = [max(values[index] - values[index - 1], 0) for index in range(1, len(values))]
    losses = [max(values[index - 1] - values[index], 0) for index in range(1, len(values))]
    for index in range(period, len(values)):
        avg_gain = sum(gains[index - period:index]) / period
        avg_loss = sum(losses[index - period:index]) / period
        output[index] = 100.0 if avg_loss == 0 else 100 - (100 / (1 + avg_gain / avg_loss))
    return output


def atr(bars: Sequence[Bar], period: int) -> NumberSeries:
    _validate_period(period)
    ranges: list[float] = []
    for index, bar in enumerate(bars):
        high, low = float(bar.high), float(bar.low)
        previous_close = float(bars[index - 1].close) if index else float(bar.close)
        ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
    return sma(ranges, period)


def rolling_vwap(bars: Sequence[Bar], period: int) -> NumberSeries:
    _validate_period(period)
    output: NumberSeries = [None] * len(bars)
    for index in range(period - 1, len(bars)):
        window = bars[index - period + 1:index + 1]
        volume = sum(float(bar.volume) for bar in window)
        if volume > 0:
            output[index] = sum(
                ((float(bar.high) + float(bar.low) + float(bar.close)) / 3) * float(bar.volume)
                for bar in window
            ) / volume
    return output


def volume_ratio(bars: Sequence[Bar], period: int) -> NumberSeries:
    _validate_period(period)
    output: NumberSeries = [None] * len(bars)
    volumes = [float(bar.volume) for bar in bars]
    for index in range(period, len(bars)):
        average = sum(volumes[index - period:index]) / period
        output[index] = volumes[index] / average if average > 0 else None
    return output


def macd(values: Sequence[float], fast: int, slow: int, signal: int) -> dict[str, NumberSeries]:
    if fast >= slow:
        raise ValueError("macd fast period must be lower than slow period")
    fast_values, slow_values = ema(values, fast), ema(values, slow)
    line: NumberSeries = [
        None if left is None or right is None else left - right
        for left, right in zip(fast_values, slow_values)
    ]
    compact = [value if value is not None else 0.0 for value in line]
    signal_values = ema(compact, signal)
    signal_values = [value if line[index] is not None else None for index, value in enumerate(signal_values)]
    histogram: NumberSeries = [
        None if value is None or signal_value is None else value - signal_value
        for value, signal_value in zip(line, signal_values)
    ]
    return {"line": line, "signal": signal_values, "histogram": histogram}


def _validate_period(period: int) -> None:
    if not 1 <= period <= 500:
        raise ValueError("indicator period must be between 1 and 500")
