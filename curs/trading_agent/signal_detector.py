# coding: utf-8
"""安全地评估 StrategySpec 条件，不使用 eval。"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from curs.domain.models import Bar, CandidateSignal
from curs.trading_agent.strategy_spec import Condition, StrategySpec


def _compare(actual: Any, operator: str, expected: Any) -> bool:
    if isinstance(actual, Decimal):
        expected = Decimal(str(expected))
    operations = {
        'eq': lambda: actual == expected,
        'ne': lambda: actual != expected,
        'gt': lambda: actual > expected,
        'gte': lambda: actual >= expected,
        'lt': lambda: actual < expected,
        'lte': lambda: actual <= expected,
    }
    return operations[operator]()


class SignalDetector:
    @staticmethod
    def _matches(condition: Condition, features: Dict[str, Any]) -> bool:
        if condition.field not in features:
            return False
        try:
            return _compare(
                features[condition.field],
                condition.operator,
                condition.value,
            )
        except (TypeError, ValueError, ArithmeticError):
            return False

    def detect(
        self,
        spec: StrategySpec,
        bar: Bar,
        features: Dict[str, Any],
    ) -> Optional[CandidateSignal]:
        if not spec.enabled or bar.timeframe != spec.timeframe:
            return None
        if not spec.accepts(str(bar.instrument), bar.instrument.asset_class, bar.instrument.venue):
            return None
        if not all(self._matches(condition, features) for condition in spec.trigger_all):
            return None
        return CandidateSignal(
            strategy_id=spec.strategy_id,
            instrument=bar.instrument,
            signal_type='ENTRY_CANDIDATE',
            bar_closed_at=bar.closed_at,
            price=bar.close,
            features=features,
        )

    @staticmethod
    def _matches(condition: Condition, features: Dict[str, Any]) -> bool:
        if condition.field not in features:
            return False
        try:
            return _compare(features[condition.field], condition.operator, condition.value)
        except (ArithmeticError, TypeError, ValueError):
            return False


class SignalDeduplicator:
    def __init__(self):
        self._seen = set()
        self._last_trigger: Dict[Tuple[str, str], datetime] = {}

    def accept(self, signal: CandidateSignal, cooldown_seconds: int) -> bool:
        if signal.signal_id in self._seen:
            return False
        key = (signal.strategy_id, str(signal.instrument))
        last_trigger = self._last_trigger.get(key)
        now = signal.bar_closed_at
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        if last_trigger and now < last_trigger + timedelta(seconds=cooldown_seconds):
            return False
        self._seen.add(signal.signal_id)
        self._last_trigger[key] = now
        return True
