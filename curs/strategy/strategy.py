# coding: utf-8
from curs.log_handler.logger import logger
from curs.events import *

class Strategy(object):
    def __init__(self, event_bus, scope, ucontext):
        self._user_context = ucontext
        self._current_universe = set()

        self._init = scope.get('init', None)
        self._handle_bar = scope.get('handle_bar', None)
        self._handle_tick = scope.get('handle_tick', None)
        func_before_trading = scope.get('before_trading', None)
        if func_before_trading is not None and func_before_trading.__code__.co_argcount > 1:
            self._before_trading = lambda context: func_before_trading(context, None)
            logger.warn((u"deprecated parameter[bar_dict] in before_trading function."))
        else:
            self._before_trading = func_before_trading
        self._after_trading = scope.get('after_trading', None)

        if self._before_trading is not None:
            event_bus.add_listener(EVENT.BEFORE_TRADING, self.before_trading)
        if self._handle_bar is not None:
            event_bus.add_listener(EVENT.BAR, self.handle_bar)
        if self._handle_tick is not None:
            event_bus.add_listener(EVENT.TICK, self.handle_tick)
        if self._after_trading is not None:
            event_bus.add_listener(EVENT.AFTER_TRADING, self.after_trading)

        self._before_day_trading = scope.get('before_day_trading', None)
        self._before_night_trading = scope.get('before_night_trading', None)
        if self._before_day_trading is not None:
            logger.warn((u"[deprecated] before_day_trading is no longer used. use before_trading instead."))
        if self._before_night_trading is not None:
            logger.warn((u"[deprecated] before_night_trading is no longer used. use before_trading instead."))
        self._force_run_before_trading = True
       # self._force_run_before_trading = Environment.get_instance().config.extra.force_run_init_when_pt_resume

    @property
    def user_context(self):
        return self._user_context

    def init(self):
        if not self._init:
            return
        self._init(self._user_context)

    def before_trading(self, event):
        self._force_run_before_trading = False
        self._before_trading(self._user_context)

    def handle_bar(self, event):
        if self._force_run_before_trading:
            self.before_trading(event)
        else:
            bar_dict = event.bar_dict
            self._handle_bar(self._user_context, bar_dict)

    def handle_tick(self, event):
        if self._force_run_before_trading:
            self.before_trading(event)
        else:
            tick = event.tick
            self._handle_tick(self._user_context, tick)

    def after_trading(self, event):
        self._after_trading(self._user_context)
        pass