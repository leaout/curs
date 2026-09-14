# coding: utf-8
"""从现有 QMT/东方财富账户构造统一风控快照。"""

from decimal import Decimal

from curs.domain.models import InstrumentId, PositionSnapshot
from curs.trading_agent.risk import RiskContext


class LegacyAccountRiskContextProvider:
    def __init__(self, account):
        self._account = account

    def __call__(self, instrument_value: str) -> RiskContext:
        instrument = InstrumentId.parse(instrument_value)
        asset = self._account.get_current_account()
        positions = self._account.get_positions()
        target_symbol = _legacy_symbol_for_instrument(instrument)
        total_exposure = Decimal('0')
        target = None

        for item in positions:
            market_value = _decimal(getattr(item, 'market_value', 0))
            total_exposure += market_value
            if str(getattr(item, 'stock_code', '')).upper() == target_symbol:
                target = PositionSnapshot(
                    instrument=instrument,
                    quantity=_decimal(getattr(item, 'volume', 0)),
                    available_quantity=_decimal(getattr(item, 'can_use_volume', 0)),
                    average_price=_decimal(getattr(item, 'open_price', 0)),
                    last_price=(
                        market_value / _decimal(getattr(item, 'volume', 0))
                        if _decimal(getattr(item, 'volume', 0)) else Decimal('0')
                    ),
                )

        total_equity = _decimal(getattr(asset, 'total_asset', 0))
        return RiskContext(
            total_equity=total_equity,
            available_cash=_decimal(getattr(asset, 'cash', 0)),
            total_exposure=total_exposure,
            symbol_exposure=target.market_value if target else Decimal('0'),
            positions_count=sum(
                1 for item in positions if _decimal(getattr(item, 'volume', 0)) > 0
            ),
            position=target,
            trading_enabled=bool(getattr(self._account, 'live_trading', False)),
        )


def _legacy_symbol_for_instrument(instrument: InstrumentId) -> str:
    if instrument.asset_class != 'CN_EQUITY':
        return instrument.symbol
    suffix = {'XSHG': 'SH', 'XSHE': 'SZ', 'XBSE': 'BJ'}.get(instrument.venue)
    if suffix is None:
        raise ValueError(f'unsupported CN venue: {instrument.venue}')
    return f'{instrument.symbol}.{suffix}'


def _decimal(value) -> Decimal:
    return Decimal(str(value or 0))
