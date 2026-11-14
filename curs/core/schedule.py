# coding: utf-8
import threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import schedule

from curs.events import EVENT, Event
from curs.log_handler.logger import logger


class EventsScheduler:
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self._scheduler = schedule.Scheduler()
        self._stop = threading.Event()
        self._scheduler.every().day.at("08:50", "Asia/Shanghai").do(self.before_trading)
        self._scheduler.every().day.at("15:15", "Asia/Shanghai").do(self.after_trading)
        self._scheduler.every().day.at("21:30", "Asia/Shanghai").do(self.research_hot_stocks)
        self._scheduler.every(15).minutes.do(self.research_hot_stocks)
        self.scheduler_thread = threading.Thread(target=self.run, daemon=True)

    def before_trading(self):
        if datetime.now(ZoneInfo('Asia/Shanghai')).weekday() < 5:
            self.event_bus.put_event(Event(EVENT.BEFORE_TRADING))

    def after_trading(self):
        if datetime.now(ZoneInfo('Asia/Shanghai')).weekday() < 5:
            self.event_bus.put_event(Event(EVENT.AFTER_TRADING))

    def run(self):
        while not self._stop.is_set():
            try:
                self._scheduler.run_pending()
            except Exception:
                logger.exception('Scheduled strategy event failed')
            self._stop.wait(1)

    def research_hot_stocks(self):
        from curs.workbuddy_desktop import start

        now = datetime.now(ZoneInfo('Asia/Shanghai'))
        cutoff = now.replace(hour=21, minute=30, second=0, microsecond=0)
        if now < cutoff:
            if now.hour >= 21:
                return  # The new hot list may be importing before the next scheduled batch.
            cutoff -= timedelta(days=1)
        try:
            start(all_stocks=True, report_day=cutoff.date().isoformat())
        except (RuntimeError, ValueError, OSError) as exc:
            logger.warning('跳过本次热点股分析：%s', exc)

    def start(self):
        self.scheduler_thread.start()

    def stop(self):
        self._stop.set()
        if self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=3)
