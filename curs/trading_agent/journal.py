# coding: utf-8
"""追加式 Trading Agent 审计日志。"""

import json
import os
import threading
from dataclasses import asdict, is_dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict


class TradingJournal:
    def __init__(self, path: str = 'data/trading_agent/events.jsonl'):
        self.path = path
        self._lock = threading.Lock()

    def append(self, event_type: str, payload: Any) -> None:
        event = {
            'event_type': event_type,
            'recorded_at': datetime.utcnow().isoformat() + 'Z',
            'payload': payload,
        }
        directory = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(directory, exist_ok=True)
        with self._lock:
            with open(self.path, 'a', encoding='utf-8') as journal_file:
                journal_file.write(json.dumps(
                    event,
                    ensure_ascii=False,
                    default=_json_default,
                    sort_keys=True,
                ))
                journal_file.write('\n')


class MemoryTradingJournal:
    def __init__(self):
        self.events = []

    def append(self, event_type: str, payload: Any) -> None:
        self.events.append({'event_type': event_type, 'payload': payload})


def _json_default(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f'cannot serialize {type(value).__name__}')
