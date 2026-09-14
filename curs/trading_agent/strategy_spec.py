# coding: utf-8
"""一句话策略生成后的安全结构化定义。"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Iterable, Tuple


ALLOWED_OPERATORS = {'eq', 'ne', 'gt', 'gte', 'lt', 'lte'}
ALLOWED_TIMEFRAMES = {'1m', '5m', '15m', '30m', '1h', '4h', '1d'}


@dataclass(frozen=True)
class Condition:
    field: str
    operator: str
    value: Any

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Condition':
        field_name = str(data.get('field', '')).strip()
        operator = str(data.get('operator', '')).strip().lower()
        if not field_name or not field_name.replace('_', '').isalnum():
            raise ValueError(f'invalid condition field: {field_name!r}')
        if operator not in ALLOWED_OPERATORS:
            raise ValueError(f'unsupported condition operator: {operator}')
        if 'value' not in data:
            raise ValueError('condition requires value')
        return cls(field=field_name, operator=operator, value=data['value'])


@dataclass(frozen=True)
class AiDecisionSpec:
    enabled: bool = True
    minimum_confidence: Decimal = Decimal('0.7')
    timeout_seconds: float = 8.0
    decision_ttl_seconds: int = 60
    cooldown_seconds: int = 600


@dataclass(frozen=True)
class PositionSpec:
    allocation_pct: Decimal = Decimal('0.1')
    max_position_pct: Decimal = Decimal('0.15')


@dataclass(frozen=True)
class StrategySpec:
    strategy_id: str
    name: str
    asset_classes: Tuple[str, ...]
    venues: Tuple[str, ...]
    instruments: Tuple[str, ...]
    timeframe: str
    trigger_all: Tuple[Condition, ...]
    ai_decision: AiDecisionSpec = AiDecisionSpec()
    position: PositionSpec = PositionSpec()
    enabled: bool = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StrategySpec':
        strategy_id = str(data.get('id') or data.get('strategy_id') or '').strip()
        if not strategy_id:
            raise ValueError('strategy id is required')

        market = data.get('market', {})
        timeframe = str(data.get('timeframe', '5m')).lower()
        if timeframe not in ALLOWED_TIMEFRAMES:
            raise ValueError(f'unsupported timeframe: {timeframe}')

        trigger = data.get('trigger', {})
        raw_conditions: Iterable[Dict[str, Any]] = trigger.get('all', [])
        conditions = tuple(Condition.from_dict(item) for item in raw_conditions)
        if not conditions:
            raise ValueError('at least one trigger condition is required')

        ai_data = data.get('ai_decision', {})
        ai_spec = AiDecisionSpec(
            enabled=bool(ai_data.get('enabled', True)),
            minimum_confidence=Decimal(str(ai_data.get('minimum_confidence', '0.7'))),
            timeout_seconds=float(ai_data.get('timeout_seconds', 8)),
            decision_ttl_seconds=int(ai_data.get('decision_ttl_seconds', 60)),
            cooldown_seconds=int(ai_data.get('cooldown_seconds', 600)),
        )
        if not Decimal('0') <= ai_spec.minimum_confidence <= Decimal('1'):
            raise ValueError('minimum_confidence must be between 0 and 1')
        if ai_spec.timeout_seconds <= 0 or ai_spec.decision_ttl_seconds <= 0:
            raise ValueError('AI timeout and decision TTL must be positive')
        if ai_spec.cooldown_seconds < 0:
            raise ValueError('AI cooldown cannot be negative')

        position_data = data.get('position', {})
        position = PositionSpec(
            allocation_pct=Decimal(str(position_data.get('allocation_pct', '0.1'))),
            max_position_pct=Decimal(str(position_data.get('max_position_pct', '0.15'))),
        )
        if not Decimal('0') < position.allocation_pct <= position.max_position_pct <= Decimal('1'):
            raise ValueError('invalid position allocation limits')

        return cls(
            strategy_id=strategy_id,
            name=str(data.get('name') or strategy_id),
            asset_classes=_upper_tuple(market.get('asset_classes', ())),
            venues=_upper_tuple(market.get('venues', ())),
            instruments=tuple(str(value).upper() for value in market.get('instruments', ())),
            timeframe=timeframe,
            trigger_all=conditions,
            ai_decision=ai_spec,
            position=position,
            enabled=bool(data.get('enabled', True)),
        )

    def accepts(self, instrument: str, asset_class: str, venue: str) -> bool:
        if self.asset_classes and asset_class.upper() not in self.asset_classes:
            return False
        if self.venues and venue.upper() not in self.venues:
            return False
        return not self.instruments or instrument.upper() in self.instruments


def _upper_tuple(values: Iterable[Any]) -> Tuple[str, ...]:
    return tuple(str(value).strip().upper() for value in values if str(value).strip())
