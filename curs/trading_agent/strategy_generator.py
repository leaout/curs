# coding: utf-8
"""将自然语言策略请求交给模型并验证为 StrategySpec。"""

import json
from typing import Any, Callable, Dict, Union

from curs.trading_agent.strategy_spec import StrategySpec


SYSTEM_INSTRUCTION = """
You compile a trading idea into a constrained JSON StrategySpec.
Never emit executable code. Use only field/operator/value conditions.
Required keys: id, name, market, timeframe, trigger.
Allowed operators: eq, ne, gt, gte, lt, lte.
If the request is ambiguous, return a JSON object with needs_clarification=true
and a concise questions array instead of inventing trading parameters.
""".strip()


class StrategyNeedsClarification(ValueError):
    def __init__(self, questions):
        super().__init__('strategy requires clarification')
        self.questions = tuple(str(question) for question in questions)


class StrategyGenerator:
    def __init__(self, completion: Callable[[Dict[str, Any]], Union[str, Dict[str, Any]]]):
        self._completion = completion

    def generate(self, user_request: str) -> StrategySpec:
        if not user_request.strip():
            raise ValueError('strategy request cannot be empty')
        response = self._completion({
            'system': SYSTEM_INSTRUCTION,
            'user_request': user_request.strip(),
        })
        data = json.loads(response) if isinstance(response, str) else response
        if not isinstance(data, dict):
            raise ValueError('strategy generator must return a JSON object')
        if data.get('needs_clarification'):
            raise StrategyNeedsClarification(data.get('questions', ()))
        return StrategySpec.from_dict(data)
