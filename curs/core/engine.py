# coding: utf-8
"""Existing strategy engine using public quotes and persistent signals."""

import logging

from curs.broker.public_quote import PublicQuoteEngine
from curs.core.schedule import EventsScheduler
from curs.market_sentiment import MarketSentimentMonitor
from curs.signal_recorder import SignalMirror

logger = logging.getLogger(__name__)


class Engine:
    _quote_engine = None

    def __init__(self, event_bus, cursglobal, use_optimized=True):
        self._event_bus = event_bus
        self._global = cursglobal
        self._scheduler = EventsScheduler(event_bus)
        self._quotes = PublicQuoteEngine(event_bus, cursglobal.config.get('market_data', {}))
        self._running = False
        self._sentiment = MarketSentimentMonitor(cursglobal.config.get('market_sentiment', {}))
        self._mirror = SignalMirror()
        Engine._quote_engine = self

    @classmethod
    def get_instance(cls):
        if cls._quote_engine is None:
            raise RuntimeError('Engine has not been initialized')
        return cls._quote_engine

    def start(self):
        if self._running:
            return
        self._running = True
        self._scheduler.start()
        self._quotes.start()
        self._sentiment.start()
        self._mirror.start()
        logger.info('Public market data engine started; live trading disabled')

    def stop(self):
        self._running = False
        self._sentiment.stop()
        self._mirror.stop()
        self._quotes.stop()
        self._scheduler.stop()
        self._event_bus.stop()

    def reload_stock_pool(self):
        self._quotes.reload_stock_pool()

    def get_quote_stats(self):
        return self._quotes.get_stats()

    def get_sentiment_status(self):
        return self._sentiment.get_status()

