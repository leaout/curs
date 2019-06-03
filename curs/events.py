# coding: utf-8

from queue import Queue, Empty
from enum import Enum
from collections import defaultdict


class Event(object):
    def __init__(self, event_type, **kwargs):
        self.__dict__ = kwargs
        self.event_type = event_type

    def __repr__(self):
        return ' '.join('{}:{}'.format(k, v) for k, v in self.__dict__.items())


class EventBus(object):

    def __init__(self):
        self._listeners = defaultdict(list)
        self.__queue = Queue()

    def add_listener(self, event_type, listener):
        self._listeners[event_type].append(listener)

    def del_listener(self, event_type, handler):
        listeners = self._listeners.get(event_type)
        if listeners is None:
            return
        if handler in listeners:
            listeners.remove(handler)
        if len(listeners) == 0:
            self._listeners.pop(event_type)

    def publish_event(self, event):
        for listener in self._listeners[event.event_type]:
            # 如果返回 True ，那么消息不再传递下去
            if listener(event):
                break

    def put_event(self, event):
        self.__queue.put(event)

    def get_event(self, event):
        event = self.__queue.get(block=True, timeout=1)
        return event

    def process(self, event):
        event = self.get_event()
        self.publish_event(event)



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