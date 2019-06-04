# coding: utf-8

from queue import Queue, Empty
from enum import Enum
from collections import defaultdict
from threading import Thread
import time

class Event(object):
    def __init__(self, event_type, **kwargs):
        self.__dict__ = kwargs
        self.event_type = event_type

    def __repr__(self):
        return ' '.join('{}:{}'.format(k, v) for k, v in self.__dict__.items())


class EventBus(object):

    def __init__(self):
        self.__listeners = defaultdict(list)
        self.__queue = Queue()
        self.__is_runing = False

    def add_listener(self, event_type, listener):
        self.__listeners[event_type].append(listener)

    def del_listener(self, event_type, handler):
        listeners = self.__listeners.get(event_type)
        if listeners is None:
            return
        if handler in listeners:
            listeners.remove(handler)
        if len(listeners) == 0:
            self.__listeners.pop(event_type)

    def publish_event(self, event):
        for listener in self.__listeners[event.event_type]:
            # 如果返回 True ，那么消息不再传递下去
            if listener(event):
                break

    def put_event(self, event):
        self.__queue.put(event)

    def get_event(self):
        event = self.__queue.get(block=True)
        return event

    def __process(self):
        while self.__is_runing:
            event = self.get_event()
            self.publish_event(event)

    def start(self):
        self.__is_runing = True
        handle_thread = Thread(target=self.__process, name="EventBus")
        handle_thread.start()

    def stop(self):
        self.__is_runing = False



class EVENT(Enum):
    # 执行handle_bar函数前触发
    # pre_bar()
    PRE_BAR = 'pre_bar'
    # 该事件会触发策略的handle_bar函数
    # bar(bar_dict)
    BAR = 'bar'
    # 执行handle_bar函数后触发
    # post_bar()
    POST_BAR = 'post_bar'

    # 执行handle_tick前触发
    PRE_TICK = 'pre_tick'
    # 该事件会触发策略的handle_tick函数
    # tick(tick)
    TICK = 'tick'
    # 执行handle_tick后触发
    POST_TICK = 'post_tick'

def parse_event(event_str):
    return EVENT[event_str.upper()]



def test_put_event(event_bus):
    while True:
        event = Event(100,data="hello")
        event_bus.put_event(event)
        time.sleep(1)

def test_get_event(data):
    print(data)

def main():
    ev_bus = EventBus()
    ev_bus.start()
    ev_bus.add_listener(100, test_get_event)

    handle_thread = Thread(target=test_put_event, name="put_event", args=(ev_bus,))
    handle_thread.start()
    time.sleep(3)
    ev_bus.del_listener(100, test_get_event)
    handle_thread.join()
    pass
if __name__ == '__main__':
    main()