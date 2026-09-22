# coding: utf-8
"""Evaluate an allowlisted strategy against the latest two closed bars."""

from datetime import timedelta
from uuid import UUID

from trading_v2.agent.models import RuleOperator, StrategyRule, StrategySpec
from trading_v2.domain.base import utc_now
from trading_v2.domain.enums import SignalSide
from trading_v2.domain.market import Bar
from trading_v2.domain.signal import Signal
from trading_v2.signals import indicators


class StrategyEvaluator:
    def evaluate(
        self,
        session_id: str,
        strategy_version: int,
        strategy: StrategySpec,
        bars: list[Bar],
    ) -> Signal | None:
        closed = sorted((bar for bar in bars if bar.is_closed), key=lambda item: item.close_time)
        if len(closed) < 2:
            return None
        exit_matches, exit_facts = self._rules_match(strategy.exit_rules, closed)
        entry_matches, entry_facts = self._rules_match(strategy.entry_rules, closed)
        if strategy.exit_rules and exit_matches:
            side, facts, label = SignalSide.EXIT, exit_facts, "退出条件成立"
        elif entry_matches:
            side, facts, label = SignalSide.BUY, entry_facts, "入场条件成立"
        else:
            return None
        latest = closed[-1]
        snapshot = {
            "open": float(latest.open), "high": float(latest.high),
            "low": float(latest.low), "close": float(latest.close),
            "volume": float(latest.volume), "rules": facts,
        }
        now = utc_now()
        return Signal(
            session_id=UUID(session_id), strategy_version=strategy_version,
            instrument=latest.instrument, timeframe=strategy.timeframe, side=side,
            strength=1.0, reason=label, bar_time=latest.close_time,
            indicators=snapshot, created_at=now,
            expires_at=now + _timeframe_duration(strategy.timeframe),
        )

    def _rules_match(self, rules: list[StrategyRule], bars: list[Bar]) -> tuple[bool, list[dict]]:
        if not rules:
            return False, []
        facts = []
        for rule in rules:
            left = self._series(rule.indicator, rule.params, bars)
            right = self._comparison_series(rule, bars)
            matched = _compare(rule.operator, left, right)
            facts.append({"indicator": rule.indicator, "operator": rule.operator.value,
                          "left": left[-1], "right": right[-1], "matched": matched})
            if not matched:
                return False, facts
        return True, facts

    def _comparison_series(self, rule: StrategyRule, bars: list[Bar]) -> list[float | None]:
        if rule.value is not None:
            return [float(rule.value)] * len(bars)
        target = (rule.compare_to or "").strip().lower()
        try:
            return [float(target)] * len(bars)
        except ValueError:
            pass
        name, _, raw_period = target.partition(":")
        params = {"period": int(raw_period)} if raw_period.isdigit() else {}
        if name == "macd_signal":
            return self._series("macd", {**rule.params, "component": "signal"}, bars)
        return self._series(name, params, bars)

    def _series(self, name: str, params: dict, bars: list[Bar]) -> list[float | None]:
        closes = [float(bar.close) for bar in bars]
        period = int(params.get("period", 20))
        if name in {"open", "high", "low", "close", "volume"}:
            return indicators.field_series(bars, name)
        if name == "ma":
            return indicators.sma(closes, period)
        if name == "ema":
            return indicators.ema(closes, period)
        if name == "rsi":
            return indicators.rsi(closes, period)
        if name == "atr":
            return indicators.atr(bars, period)
        if name == "vwap":
            return indicators.rolling_vwap(bars, period)
        if name == "volume_ratio":
            return indicators.volume_ratio(bars, period)
        if name == "macd":
            values = indicators.macd(closes, int(params.get("fast", 12)),
                                     int(params.get("slow", 26)), int(params.get("signal", 9)))
            component = str(params.get("component", "line"))
            if component not in values:
                raise ValueError(f"unsupported macd component: {component}")
            return values[component]
        raise ValueError(f"unsupported indicator reference: {name}")


def _compare(operator: RuleOperator, left: list[float | None], right: list[float | None]) -> bool:
    current_left, current_right = left[-1], right[-1]
    if current_left is None or current_right is None:
        return False
    if operator == RuleOperator.GT:
        return current_left > current_right
    if operator == RuleOperator.GTE:
        return current_left >= current_right
    if operator == RuleOperator.LT:
        return current_left < current_right
    if operator == RuleOperator.LTE:
        return current_left <= current_right
    previous_left, previous_right = left[-2], right[-2]
    if previous_left is None or previous_right is None:
        return False
    if operator == RuleOperator.CROSS_ABOVE:
        return previous_left <= previous_right and current_left > current_right
    return previous_left >= previous_right and current_left < current_right


def _timeframe_duration(timeframe: str) -> timedelta:
    units = {"m": 60, "h": 3_600, "d": 86_400}
    return timedelta(seconds=int(timeframe[:-1]) * units[timeframe[-1]])
