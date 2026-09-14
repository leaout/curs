# coding: utf-8
"""AI 决策协议和严格结构化输出解析。"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Callable, Dict, Protocol

from curs.domain.models import Action, CandidateSignal, Decision
from curs.trading_agent.strategy_spec import StrategySpec


class DecisionProvider(Protocol):
    def decide(self, context: Dict[str, Any]) -> Decision:
        ...


class HoldDecisionProvider:
    """未配置 AI 时的安全默认实现。"""

    def decide(self, context: Dict[str, Any]) -> Decision:
        signal = context['signal']
        return Decision(
            signal_id=signal['signal_id'],
            action=Action.HOLD,
            confidence=Decimal('1'),
            reason_codes=('AI_NOT_CONFIGURED',),
            summary='AI decision provider is not configured.',
        )


class StructuredDecisionProvider:
    """将任意模型调用函数约束为 Trading Agent 的 Decision。"""

    def __init__(self, completion: Callable[[Dict[str, Any]], Dict[str, Any]]):
        self._completion = completion

    def decide(self, context: Dict[str, Any]) -> Decision:
        payload = self._completion(context)
        if not isinstance(payload, dict):
            raise ValueError('AI decision must be a JSON object')
        try:
            return Decision(
                signal_id=str(payload['signal_id']),
                action=Action(str(payload['action']).upper()),
                confidence=Decimal(str(payload['confidence'])),
                reason_codes=tuple(str(value) for value in payload.get('reason_codes', ())),
                summary=str(payload.get('summary', '')),
                position_pct=Decimal(str(payload.get('position_pct', '0'))),
                limit_price=(
                    Decimal(str(payload['limit_price']))
                    if payload.get('limit_price') is not None else None
                ),
                valid_for_seconds=int(payload.get('valid_for_seconds', 60)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f'invalid AI decision: {exc}') from exc


def build_decision_context(
    signal: CandidateSignal,
    spec: StrategySpec,
    account: Dict[str, Any],
    market: Dict[str, Any] = None,
) -> Dict[str, Any]:
    return {
        'strategy': {
            'id': spec.strategy_id,
            'name': spec.name,
            'timeframe': spec.timeframe,
        },
        'signal': {
            'signal_id': signal.signal_id,
            'signal_type': signal.signal_type,
            'instrument': str(signal.instrument),
            'bar_closed_at': signal.bar_closed_at.isoformat(),
            'price': str(signal.price),
            'features': {
                key: str(value) if isinstance(value, Decimal) else value
                for key, value in signal.features.items()
            },
        },
        'account': account,
        'market': market or {},
        'output_contract': {
            'actions': [action.value for action in Action],
            'required': ['signal_id', 'action', 'confidence'],
        },
    }


def validate_decision(
    decision: Decision,
    signal: CandidateSignal,
    spec: StrategySpec,
    now: datetime,
) -> None:
    if decision.signal_id != signal.signal_id:
        raise ValueError('AI decision signal_id does not match candidate signal')
    if decision.confidence < spec.ai_decision.minimum_confidence:
        raise ValueError('AI confidence is below strategy threshold')
    if decision.valid_for_seconds > spec.ai_decision.decision_ttl_seconds:
        raise ValueError('AI decision TTL exceeds strategy limit')
    age_seconds = (now - decision.created_at).total_seconds()
    if age_seconds > decision.valid_for_seconds:
        raise ValueError('AI decision has expired')
