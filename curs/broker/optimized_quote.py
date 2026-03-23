# coding: utf-8
import logging
import time
from datetime import datetime, time as dt_time
from functools import partial
from threading import Thread, Lock
from queue import Queue
from collections import defaultdict

from xtquant import xtdata
from curs.events import *
from curs.database import get_db_manager

logger = logging.getLogger(__name__)


class OptimizedQuoteEngine:
    """
    优化版行情引擎
    优化点：
    1. 只订阅热点股票池（200-500只），而非全市场5000+
    2. 预处理tick数据，减少无效计算
    3. 使用队列批量投递事件
    4. 独立线程处理tick推送
    """
    
    def __init__(self, event_bus, stock_pool_name: str = 'hot', max_queue_size: int = 100):
        self.event_bus = event_bus
        self.stock_pool_name = stock_pool_name
        
        self.stocks = []  # 订阅的股票列表
        self.stock_set = set()  # 用于快速查找
        
        self._running = False
        self._worker_thread = None
        self._tick_queue = Queue(maxsize=max_queue_size)
        
        self._last_update_time = {}  # 每只股票上次更新时间
        self._tick_count = 0
        self._filter_count = 0
        
        # 交易时间段
        self.trading_morning_start = dt_time(9, 30)
        self.trading_morning_end = dt_time(11, 30)
        self.trading_afternoon_start = dt_time(13, 0)
        self.trading_afternoon_end = dt_time(15, 0)
        
    def _is_trading_time(self) -> bool:
        """判断当前是否在交易时间"""
        now = datetime.now().time()
        if self.trading_morning_start <= now <= self.trading_morning_end:
            return True
        if self.trading_afternoon_start <= now <= self.trading_afternoon_end:
            return True
        return False
    
    def _load_stock_pool(self):
        """从数据库加载热点股票池"""
        try:
            db_manager = get_db_manager()
            if db_manager and db_manager.connection:
                stocks = db_manager.get_hot_stocks_from_pool(self.stock_pool_name)
                if stocks:
                    self.stocks = stocks
                    self.stock_set = set(stocks)
                    logger.info(f"从数据库加载股票池 '{self.stock_pool_name}'，共 {len(self.stocks)} 只")
                    return
        
        except Exception as e:
            logger.warning(f"从数据库加载股票池失败: {e}")
        
        # 降级：使用本地文件
        try:
            with open('data/hotstocks.txt', 'r') as f:
                self.stocks = [line.strip() for line in f if line.strip()]
                self.stock_set = set(self.stocks)
            logger.info(f"从本地文件加载股票池，共 {len(self.stocks)} 只")
        except Exception as e:
            logger.warning(f"加载本地股票池失败: {e}")
            self.stocks = xtdata.get_stock_list_in_sector("沪深A股")[:300]
            self.stock_set = set(self.stocks)
            logger.info(f"使用默认股票池，共 {len(self.stocks)} 只")
    
    def _pre_filter_tick(self, tick_data: dict) -> dict:
        """
        预处理tick数据，过滤无效数据
        返回需要处理的股票
        """
        filtered = {}
        
        for stock_code, data in tick_data.items():
            # 1. 跳过非热点股票
            if stock_code not in self.stock_set:
                continue
            
            # 2. 跳过非交易时间的数据
            tick_time = data.get('time', 0)
            if tick_time:
                tick_datetime = datetime.fromtimestamp(tick_time / 1000)
                tick_time_only = tick_datetime.time()
                if not (self.trading_morning_start <= tick_time_only <= self.trading_morning_end or 
                        self.trading_afternoon_start <= tick_time_only <= self.trading_afternoon_end):
                    continue
            
            # 3. 跳过无变化的数据（可选）
            last_time = self._last_update_time.get(stock_code, 0)
            if tick_time and tick_time <= last_time:
                self._filter_count += 1
                continue
            
            if tick_time:
                self._last_update_time[stock_code] = tick_time
            
            filtered[stock_code] = data
        
        return filtered
    
    def _on_tick_data(self, datas: dict):
        """Tick数据回调 - 预处理后放入队列"""
        self._tick_count += 1
        
        # 预处理过滤
        filtered_data = self._pre_filter_tick(datas)
        
        if not filtered_data:
            return
        
        # 放入队列（非阻塞）
        try:
            self._tick_queue.put_nowait(filtered_data)
        except:
            # 队列满，丢弃最旧的数据
            try:
                self._tick_queue.get_nowait()
                self._tick_queue.put_nowait(filtered_data)
            except:
                pass
    
    def _worker_loop(self):
        """工作线程：从队列取数据并投递事件"""
        while self._running:
            try:
                # 从队列获取数据（带超时）
                tick_data = self._tick_queue.get(timeout=1)
                
                if tick_data:
                    self.event_bus.put_event(Event(EVENT.TICK, tick=tick_data))
                    
            except:
                continue
    
    def start(self):
        """启动行情引擎"""
        if self._running:
            return
        
        # 加载股票池
        self._load_stock_pool()
        
        if not self.stocks:
            logger.error("股票池为空，无法启动行情引擎")
            return
        
        self._running = True
        
        # 启动工作线程
        self._worker_thread = Thread(target=self._worker_loop, daemon=True, name="QuoteWorker")
        self._worker_thread.start()
        
        # 订阅行情
        try:
            callback = partial(self._on_tick_data)
            sid = xtdata.subscribe_whole_quote(self.stocks, callback=callback)
            logger.info(f"优化行情订阅成功，股票数: {len(self.stocks)}, 订阅ID: {sid}")
        except Exception as e:
            logger.error(f"行情订阅失败: {e}")
            self._running = False
            raise
    
    def stop(self):
        """停止行情引擎"""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5)
        logger.info(f"优化行情引擎已停止，收到tick数: {self._tick_count}, 过滤数: {self._filter_count}")
    
    def reload_stock_pool(self):
        """重新加载股票池"""
        old_count = len(self.stocks)
        self._load_stock_pool()
        if len(self.stocks) != old_count:
            logger.info(f"股票池已更新: {old_count} -> {len(self.stocks)}")
            # 重新订阅
            try:
                if self._running:
                    self.stop()
                    time.sleep(1)
                    self.start()
            except Exception as e:
                logger.error(f"重新订阅失败: {e}")
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "subscribed_stocks": len(self.stocks),
            "total_ticks": self._tick_count,
            "filtered_ticks": self._filter_count,
            "queue_size": self._tick_queue.qsize(),
            "running": self._running
        }


class TickBatchProcessor:
    """
    Tick批量处理器
    将多个tick合并处理，减少事件投递次数
    """
    
    def __init__(self, event_bus, batch_interval: float = 0.1):
        self.event_bus = event_bus
        self.batch_interval = batch_interval
        
        self._buffer = {}
        self._running = False
        self._worker_thread = None
        self._lock = Lock()
        
    def add_tick(self, tick_data: dict):
        """添加tick数据到缓冲区"""
        with self._lock:
            for stock_code, data in tick_data.items():
                # 保留最新的数据
                self._buffer[stock_code] = data
    
    def _flush(self):
        """刷新缓冲区，投递事件"""
        with self._lock:
            if not self._buffer:
                return
            
            data = self._buffer
            self._buffer = {}
        
        if data:
            self.event_bus.put_event(Event(EVENT.TICK, tick=data))
    
    def _worker_loop(self):
        """定时刷新线程"""
        import time
        while self._running:
            try:
                self._flush()
                time.sleep(self.batch_interval)
            except:
                continue
    
    def start(self):
        """启动"""
        self._running = True
        self._worker_thread = Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
    
    def stop(self):
        """停止"""
        self._running = False
        self._flush()  # 最后一次刷新


# 兼容旧接口
def record_tick_optimized(event_bus, stock_pool_name: str = 'hot'):
    """优化的行情记录函数"""
    engine = OptimizedQuoteEngine(event_bus, stock_pool_name)
    engine.start()
    return engine
