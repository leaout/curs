# coding: utf-8
import logging
from queue import Queue, Empty
from threading import Thread, Lock
from concurrent.futures import ThreadPoolExecutor, Future
from collections import defaultdict
from typing import Callable, Dict, List
import time

logger = logging.getLogger(__name__)


class ParallelEventBus:
    """
    并行事件总线
    优化点：
    1. 使用线程池并行处理事件
    2. 支持批量处理
    3. 事件优先级
    4. 事件防抖
    """
    
    def __init__(self, max_workers: int = 4, queue_size: int = 1000):
        self._listeners = defaultdict(list)
        self._event_queue = Queue(maxsize=queue_size)
        self._is_running = False
        self._worker_thread = None
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="EventWorker")
        
        self._stats = {
            'processed': 0,
            'failed': 0,
            'queued': 0
        }
        self._stats_lock = Lock()
    
    def add_listener(self, event_type: str, listener: Callable):
        """添加事件监听器"""
        self._listeners[event_type].append(listener)
    
    def del_listener(self, event_type: str, listener: Callable):
        """删除事件监听器"""
        listeners = self._listeners.get(event_type)
        if listeners and listener in listeners:
            listeners.remove(listener)
    
    def put_event(self, event):
        """投递事件（非阻塞）"""
        try:
            self._event_queue.put_nowait(event)
            with self._stats_lock:
                self._stats['queued'] += 1
        except:
            logger.warning("事件队列已满，丢弃事件")
    
    def _process_event(self, event):
        """处理单个事件"""
        event_type = event.event_type
        listeners = self._listeners.get(event_type, [])
        
        if not listeners:
            return
        
        # 并行执行所有监听器
        futures = []
        for listener in listeners:
            try:
                future = self._executor.submit(listener, event)
                futures.append(future)
            except Exception as e:
                logger.error(f"提交事件处理任务失败: {e}")
        
        # 等待完成（可选，不等待以提高吞吐量）
        # for future in futures:
        #     try:
        #         future.result(timeout=5)
        #     except Exception as e:
        #         logger.error(f"事件处理失败: {e}")
    
    def _worker_loop(self):
        """工作循环"""
        while self._is_running:
            try:
                event = self._event_queue.get(timeout=1)
                
                self._process_event(event)
                
                with self._stats_lock:
                    self._stats['processed'] += 1
                    
            except Empty:
                continue
            except Exception as e:
                logger.error(f"事件处理循环异常: {e}")
                with self._stats_lock:
                    self._stats['failed'] += 1
    
    def start(self):
        """启动事件总线"""
        if self._is_running:
            return
        
        self._is_running = True
        self._worker_thread = Thread(target=self._worker_loop, daemon=True, name="EventBusWorker")
        self._worker_thread.start()
        logger.info("并行事件总线已启动")
    
    def stop(self):
        """停止事件总线"""
        self._is_running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5)
        self._executor.shutdown(wait=True)
        logger.info(f"并行事件总线已停止，处理事件: {self._stats['processed']}, 失败: {self._stats['failed']}")
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        with self._stats_lock:
            return dict(self._stats)


class FastEventProcessor:
    """
    快速事件处理器
    优化策略：
    1. 按股票分组处理tick
    2. 预过滤无效事件
    3. 批量处理
    """
    
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self._handlers = {}
        self._pre_filters = []
    
    def register_handler(self, event_type: str, handler: Callable, priority: int = 0):
        """注册处理器"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append((priority, handler))
        # 按优先级排序
        self._handlers[event_type].sort(key=lambda x: -x[0])
    
    def add_pre_filter(self, filter_func: Callable):
        """添加预过滤函数"""
        self._pre_filters.append(filter_func)
    
    def process(self, event):
        """处理事件"""
        # 预过滤
        for filter_func in self._pre_filters:
            if not filter_func(event):
                return
        
        # 分发处理
        event_type = event.event_type
        handlers = self._handlers.get(event_type, [])
        
        for _, handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"事件处理异常: {e}")


class TickCache:
    """
    Tick数据缓存
    避免重复计算，只处理有变化的股票
    """
    
    def __init__(self, ttl_seconds: float = 1.0):
        self._cache = {}
        self._ttl = ttl_seconds
        self._lock = Lock()
    
    def update(self, stock_code: str, tick_data: dict) -> bool:
        """
        更新缓存
        返回True表示数据有变化，False表示无变化
        """
        with self._lock:
            old_data = self._cache.get(stock_code)
            
            # 简单比较：时间或价格变化
            if old_data:
                if old_data.get('time') == tick_data.get('time'):
                    return False
                
                old_price = old_data.get('lastPrice', 0)
                new_price = tick_data.get('lastPrice', 0)
                if old_price == new_price and old_data.get('time') == tick_data.get('time'):
                    return False
            
            self._cache[stock_code] = tick_data.copy()
            return True
    
    def get(self, stock_code: str) -> dict:
        """获取缓存数据"""
        with self._lock:
            return self._cache.get(stock_code)
    
    def get_changed(self, tick_data: dict) -> dict:
        """获取有变化的数据"""
        changed = {}
        for stock_code, data in tick_data.items():
            if self.update(stock_code, data):
                changed[stock_code] = data
        return changed
    
    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
