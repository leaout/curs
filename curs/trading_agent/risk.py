# coding: utf-8
"""不可被 AI 或策略绕过的分层硬风控。"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import FrozenSet, Optional, Tuple

from curs.domain.models import OrderIntent, PositionSnapshot, Side


@dataclass(frozen=True)
class RiskLimits:
    max_single_order_value: Decimal = Decimal('10000')
    max_symbol_exposure_pct: Decimal = Decimal('0.15')
    max_total_exposure_pct: Decimal = Decimal('0.50')
    max_positions: int = 5
    max_daily_loss_pct: Decimal = Decimal('0.02')
    max_market_data_age_seconds: int = 90


@dataclass(frozen=True)
class RiskContext:
    total_equity: Decimal
    available_cash: Decimal
    total_exposure: Decimal = Decimal('0')
    symbol_exposure: Decimal = Decimal('0')
    daily_pnl: Decimal = Decimal('0')
    positions_count: int = 0
    market_data_age_seconds: int = 0
    position: Optional[PositionSnapshot] = None
    pending_signal_ids: FrozenSet[str] = field(default_factory=frozenset)
    trading_enabled: bool = False
    kill_switch: bool = False


@dataclass(frozen=True)
class RiskResult:
    approved: bool
    reason_codes: Tuple[str, ...] = ()


class RiskGate:
    def __init__(self, limits: RiskLimits = None):
        self.limits = limits or RiskLimits()

    def evaluate(self, intent: OrderIntent, context: RiskContext) -> RiskResult:
        reasons = []
        price = intent.limit_price or intent.reference_price
        order_value = intent.quantity * price

        if not context.trading_enabled:
            reasons.append('LIVE_TRADING_DISABLED')
        if context.kill_switch:
            reasons.append('KILL_SWITCH_ACTIVE')
        if intent.signal_id in context.pending_signal_ids:
            reasons.append('DUPLICATE_PENDING_SIGNAL')
        if context.market_data_age_seconds > self.limits.max_market_data_age_seconds:
            reasons.append('STALE_MARKET_DATA')
        if order_value > self.limits.max_single_order_value:
            reasons.append('MAX_SINGLE_ORDER_VALUE')

        if context.total_equity <= 0:
            reasons.append('INVALID_ACCOUNT_EQUITY')
        else:
            if context.daily_pnl < -(context.total_equity * self.limits.max_daily_loss_pct):
                reasons.append('MAX_DAILY_LOSS')
            if context.symbol_exposure + order_value > (
                context.total_equity * self.limits.max_symbol_exposure_pct
            ) and intent.side == Side.BUY:
                reasons.append('MAX_SYMBOL_EXPOSURE')
            if context.total_exposure + order_value > (
                context.total_equity * self.limits.max_total_exposure_pct
            ) and intent.side == Side.BUY:
                reasons.append('MAX_TOTAL_EXPOSURE')

        if intent.side == Side.BUY:
            if order_value > context.available_cash:
                reasons.append('INSUFFICIENT_CASH')
            if context.position is None and context.positions_count >= self.limits.max_positions:
                reasons.append('MAX_POSITIONS')
        elif intent.side == Side.SELL:
            if context.position is None:
                reasons.append('POSITION_NOT_FOUND')
            elif intent.quantity > context.position.available_quantity:
                reasons.append('INSUFFICIENT_AVAILABLE_POSITION')

        return RiskResult(approved=not reasons, reason_codes=tuple(reasons))
