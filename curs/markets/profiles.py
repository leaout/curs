# coding: utf-8
"""不同资产市场的交易能力与数量、价格约束。"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from typing import Dict, Iterable

from curs.domain.models import InstrumentId


@dataclass(frozen=True)
class MarketProfile:
    asset_class: str
    timezone: str
    session_type: str
    settlement_cycle: str
    quantity_step: Decimal
    price_tick: Decimal
    supports_short: bool = False
    supports_fractional: bool = False
    supports_leverage: bool = False

    def normalize_quantity(self, quantity: Decimal) -> Decimal:
        if quantity <= 0 or self.quantity_step <= 0:
            return Decimal('0')
        steps = (quantity / self.quantity_step).to_integral_value(
            rounding=ROUND_DOWN
        )
        return steps * self.quantity_step

    def normalize_price(self, price: Decimal) -> Decimal:
        if price <= 0 or self.price_tick <= 0:
            return Decimal('0')
        ticks = (price / self.price_tick).to_integral_value(
            rounding=ROUND_DOWN
        )
        return ticks * self.price_tick


class MarketRegistry:
    def __init__(self, profiles: Iterable[MarketProfile] = ()):
        self._profiles: Dict[str, MarketProfile] = {}
        for profile in profiles:
            self.register(profile)

    def register(self, profile: MarketProfile) -> None:
        self._profiles[profile.asset_class.upper()] = profile

    def get(self, instrument: InstrumentId) -> MarketProfile:
        try:
            return self._profiles[instrument.asset_class]
        except KeyError as exc:
            raise ValueError(
                f'no market profile for {instrument.asset_class}'
            ) from exc

    @classmethod
    def defaults(cls) -> 'MarketRegistry':
        return cls([
            MarketProfile(
                asset_class='CN_EQUITY',
                timezone='Asia/Shanghai',
                session_type='SESSION_BASED',
                settlement_cycle='T+1',
                quantity_step=Decimal('100'),
                price_tick=Decimal('0.01'),
            ),
            MarketProfile(
                asset_class='US_EQUITY',
                timezone='America/New_York',
                session_type='SESSION_BASED',
                settlement_cycle='T+1',
                quantity_step=Decimal('1'),
                price_tick=Decimal('0.01'),
                supports_short=True,
            ),
            MarketProfile(
                asset_class='CRYPTO',
                timezone='UTC',
                session_type='ALWAYS_OPEN',
                settlement_cycle='INSTANT',
                quantity_step=Decimal('0.000001'),
                price_tick=Decimal('0.01'),
                supports_fractional=True,
            ),
            MarketProfile(
                asset_class='FX',
                timezone='UTC',
                session_type='WEEKDAY_CONTINUOUS',
                settlement_cycle='BROKER_DEFINED',
                quantity_step=Decimal('1000'),
                price_tick=Decimal('0.00001'),
                supports_short=True,
                supports_leverage=True,
            ),
        ])
