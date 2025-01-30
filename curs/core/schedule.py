import schedule
import time
from datetime import datetime
import threading
from curs.events import *

class EventsScheduler:
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.setup_schedule()
        self.scheduler_thread = threading.Thread(target=self.run)
        self.scheduler_thread.daemon = True  # 设置为守护线程，主线程结束时自动退出

    def setup_schedule(self):
        schedule.every().day.at("08:50").do(self.before_trading)
        schedule.every().day.at("15:15").do(self.after_trading)

    def before_trading(self):
        print(f"{datetime.now()}: {EVENT.EVENT_BEFORE_TRADING} 触发")
        # 在这里添加策略的预处理逻辑
        self.event_bus.publish(EVENT.EVENT_BEFORE_TRADING)

    def after_trading(self):
        print(f"{datetime.now()}: {EVENT.EVENT_AFTER_TRADING} 触发")
        # 在这里添加策略的后处理逻辑
        self.event_bus.publish(EVENT.EVENT_AFTER_TRADING)

    def run(self):
        while True:
            schedule.run_pending()
            time.sleep(1)

    def start(self):
        self.scheduler_thread.start()