# coding: utf-8
"""V2 行情接口与数据源适配器。"""

from trading_v2.market.cpptdx import CppTdxMarketDataProvider
from trading_v2.market.provider import MarketDataHealth, MarketDataProvider

__all__ = [
    'CppTdxMarketDataProvider',
    'MarketDataHealth',
    'MarketDataProvider',
]
