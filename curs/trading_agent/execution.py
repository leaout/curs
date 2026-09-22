# coding: utf-8
"""标准订单执行协议和现有 Curs 账户兼容适配器。"""

from dataclasses import dataclass
from typing import Any, Protocol

from curs.domain.models import OrderIntent, OrderType, Side


@dataclass(frozen=True)
class ExecutionResult:
    accepted: bool
    broker_order_id: str = ''
    message: str = ''


class BrokerAdapter(Protocol):
    def place_order(self, intent: OrderIntent) -> ExecutionResult:
        ...


class LegacyAccountBrokerAdapter:
    """让保留的账户实现接受统一 OrderIntent。"""

    def __init__(self, account: Any):
        self._account = account

    def place_order(self, intent: OrderIntent) -> ExecutionResult:
        symbol = _legacy_symbol(intent)
        quantity = int(intent.quantity)
        price = float(intent.limit_price or 0)
        if intent.side == Side.BUY:
            if intent.order_type == OrderType.LIMIT:
                result = self._account.buy_fix_price(symbol, quantity, price)
            else:
                result = self._account.buy_latest_price(symbol, quantity)
        else:
            if intent.order_type == OrderType.LIMIT:
                result = self._account.sell_fix_price(symbol, quantity, price)
            else:
                result = self._account.sell_latest_price(symbol, quantity)
        return ExecutionResult(
            accepted=bool(result),
            broker_order_id=str(result or ''),
            message='accepted' if result else 'broker rejected order',
        )


class PaperBrokerAdapter:
    """不访问真实券商的模拟成交适配器。"""

    def __init__(self):
        self.orders = []

    def place_order(self, intent: OrderIntent) -> ExecutionResult:
        self.orders.append(intent)
        return ExecutionResult(
            accepted=True,
            broker_order_id=f'paper-{intent.intent_id}',
            message='paper order accepted',
        )


class ExecutionEngine:
    def __init__(self, broker: BrokerAdapter):
        self._broker = broker
        self._submitted_intents = set()

    def execute(self, intent: OrderIntent) -> ExecutionResult:
        if intent.intent_id in self._submitted_intents:
            return ExecutionResult(False, message='duplicate intent_id')
        self._submitted_intents.add(intent.intent_id)
        return self._broker.place_order(intent)


def _legacy_symbol(intent: OrderIntent) -> str:
    instrument = intent.instrument
    if instrument.asset_class == 'CN_EQUITY':
        suffixes = {'XSHG': 'SH', 'XSHE': 'SZ', 'XBSE': 'BJ'}
        suffix = suffixes.get(instrument.venue)
        if not suffix:
            raise ValueError(f'unsupported CN venue: {instrument.venue}')
        return f'{instrument.symbol}.{suffix}'
    return instrument.symbol
