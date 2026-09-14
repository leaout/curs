# coding: utf-8
"""与具体市场和券商无关的核心交易模型。"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Optional, Tuple
from uuid import uuid4


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Side(str, Enum):
    BUY = 'BUY'
    SELL = 'SELL'


class Action(str, Enum):
    BUY = 'BUY'
    SELL = 'SELL'
    REDUCE = 'REDUCE'
    HOLD = 'HOLD'
    CANCEL = 'CANCEL'


class OrderType(str, Enum):
    MARKET = 'MARKET'
    LIMIT = 'LIMIT'


@dataclass(frozen=True)
class InstrumentId:
    """标准标的编码，例如 ``CRYPTO:BINANCE:BTC-USDT``。"""

    asset_class: str
    venue: str
    symbol: str

    def __post_init__(self) -> None:
        for name, value in (
            ('asset_class', self.asset_class),
            ('venue', self.venue),
            ('symbol', self.symbol),
        ):
            if not value or ':' in value:
                raise ValueError(f'invalid {name}: {value!r}')
            object.__setattr__(self, name, value.strip().upper())

    @classmethod
    def parse(cls, value: str) -> 'InstrumentId':
        parts = value.split(':', 2)
        if len(parts) != 3:
            raise ValueError(
                'instrument must use ASSET_CLASS:VENUE:SYMBOL format'
            )
        return cls(*parts)

    def __str__(self) -> str:
        return f'{self.asset_class}:{self.venue}:{self.symbol}'


@dataclass(frozen=True)
class Bar:
    instrument: InstrumentId
    timeframe: str
    opened_at: datetime
    closed_at: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    is_closed: bool = True

    def __post_init__(self) -> None:
        if self.high < max(self.open, self.close, self.low):
            raise ValueError('bar high is below OHLC values')
        if self.low > min(self.open, self.close, self.high):
            raise ValueError('bar low is above OHLC values')
        if self.volume < 0:
            raise ValueError('bar volume cannot be negative')


@dataclass(frozen=True)
class TradeTick:
    instrument: InstrumentId
    timestamp: datetime
    price: Decimal
    volume: Decimal = Decimal('0')

    def __post_init__(self) -> None:
        if self.price <= 0:
            raise ValueError('tick price must be positive')
        if self.volume < 0:
            raise ValueError('tick volume cannot be negative')


@dataclass(frozen=True)
class CandidateSignal:
    strategy_id: str
    instrument: InstrumentId
    signal_type: str
    bar_closed_at: datetime
    price: Decimal
    features: Dict[str, Any]
    signal_id: str = ''

    def __post_init__(self) -> None:
        if not self.signal_id:
            fingerprint = (
                f'{self.strategy_id}:{self.instrument}:'
                f'{self.signal_type}:{self.bar_closed_at.isoformat()}'
            )
            object.__setattr__(self, 'signal_id', fingerprint)


@dataclass(frozen=True)
class Decision:
    signal_id: str
    action: Action
    confidence: Decimal
    reason_codes: Tuple[str, ...] = ()
    summary: str = ''
    position_pct: Decimal = Decimal('0')
    limit_price: Optional[Decimal] = None
    valid_for_seconds: int = 60
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not Decimal('0') <= self.confidence <= Decimal('1'):
            raise ValueError('confidence must be between 0 and 1')
        if not Decimal('0') <= self.position_pct <= Decimal('1'):
            raise ValueError('position_pct must be between 0 and 1')
        if self.valid_for_seconds <= 0:
            raise ValueError('valid_for_seconds must be positive')


@dataclass(frozen=True)
class PositionSnapshot:
    instrument: InstrumentId
    quantity: Decimal
    available_quantity: Decimal
    average_price: Decimal
    last_price: Decimal

    @property
    def market_value(self) -> Decimal:
        return self.quantity * self.last_price


@dataclass(frozen=True)
class OrderIntent:
    agent_id: str
    signal_id: str
    account_id: str
    instrument: InstrumentId
    side: Side
    order_type: OrderType
    quantity: Decimal
    reference_price: Decimal
    limit_price: Optional[Decimal] = None
    reduce_only: bool = False
    expires_at: Optional[datetime] = None
    intent_id: str = field(default_factory=lambda: uuid4().hex)

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError('order quantity must be positive')
        if self.reference_price <= 0:
            raise ValueError('order reference_price must be positive')
        if self.order_type == OrderType.LIMIT and self.limit_price is None:
            raise ValueError('limit order requires limit_price')
