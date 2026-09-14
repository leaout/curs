# coding: utf-8
"""将 AI 决策转换为符合市场规格的标准订单。"""

from datetime import timedelta
from decimal import Decimal
from typing import Optional

from curs.domain.models import (
    Action,
    CandidateSignal,
    Decision,
    OrderIntent,
    OrderType,
    Side,
)
from curs.markets.profiles import MarketProfile
from curs.trading_agent.risk import RiskContext
from curs.trading_agent.strategy_spec import StrategySpec


class CapitalAllocator:
    def create_intent(
        self,
        decision: Decision,
        signal: CandidateSignal,
        spec: StrategySpec,
        market: MarketProfile,
        context: RiskContext,
        account_id: str,
    ) -> Optional[OrderIntent]:
        if decision.action in (Action.HOLD, Action.CANCEL):
            return None

        if decision.action == Action.BUY:
            allocation = decision.position_pct or spec.position.allocation_pct
            allocation = min(allocation, spec.position.max_position_pct)
            budget = min(context.available_cash, context.total_equity * allocation)
            quantity = market.normalize_quantity(budget / signal.price)
            side = Side.BUY
        else:
            if context.position is None:
                return None
            quantity = context.position.available_quantity
            if decision.action == Action.REDUCE:
                quantity = market.normalize_quantity(quantity / Decimal('2'))
            side = Side.SELL

        if quantity <= 0:
            return None

        limit_price = None
        order_type = OrderType.MARKET
        if decision.limit_price is not None:
            limit_price = market.normalize_price(decision.limit_price)
            order_type = OrderType.LIMIT

        return OrderIntent(
            agent_id=spec.strategy_id,
            signal_id=signal.signal_id,
            account_id=account_id,
            instrument=signal.instrument,
            side=side,
            order_type=order_type,
            quantity=quantity,
            reference_price=signal.price,
            limit_price=limit_price,
            reduce_only=side == Side.SELL,
            expires_at=decision.created_at + timedelta(
                seconds=decision.valid_for_seconds
            ),
        )
