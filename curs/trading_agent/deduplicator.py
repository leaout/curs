# coding: utf-8
"""候选信号幂等与冷却控制。"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Set, Tuple

from curs.domain.models import CandidateSignal


class SignalDeduplicator:
    def __init__(self):
        self._seen: Set[str] = set()
        self._last_processed: Dict[Tuple[str, str, str], datetime] = {}

    def accept(self, signal: CandidateSignal, cooldown_seconds: int) -> bool:
        if signal.signal_id in self._seen:
            return False
        key = (signal.strategy_id, str(signal.instrument), signal.signal_type)
        previous = self._last_processed.get(key)
        if previous is not None:
            elapsed = (signal.bar_closed_at - previous).total_seconds()
            if elapsed < cooldown_seconds:
                return False
        self._seen.add(signal.signal_id)
        self._last_processed[key] = signal.bar_closed_at
        return True
