# coding: utf-8
import logging
import time
import threading
from datetime import datetime
from collections import defaultdict
from typing import Dict, Optional, Callable

logger = logging.getLogger(__name__)


class OrderStatus:
    PENDING = "PENDING"           # 待成交
    PARTIAL = "PARTIAL"           # 部分成交
    FULL = "FULL"                 # 全部成交
    CANCELLED = "CANCELLED"       # 已撤单
    REJECTED = "REJECTED"         # 拒绝
    TIMEOUT = "TIMEOUT"            # 超时未成交


class OrderInfo:
    def __init__(self, stock_code: str, order_id: str, volume: int, 
                 price: float, order_type: str, order_time: datetime = None):
        self.stock_code = stock_code
        self.order_id = order_id
        self.volume = volume
        self.price = price
        self.order_type = order_type
        self.order_time = order_time or datetime.now()
        
        self.status = OrderStatus.PENDING
        self.filled_volume = 0
        self.avg_price = price
        
        self.last_update_time = self.order_time
        self.cancel_count = 0
        
        self.price_history = []  # [(timestamp, price), ...]
        self.profit_history = []  # [(timestamp, profit_pct), ...]


class OrderTracker:
    """
    订单状态跟踪器
    功能：
    1. 跟踪订单状态变化
    2. 挂单超时自动撤单重排
    3. 记录盈利时间曲线
    """
    
    def __init__(self, max_wait_seconds: int = 30, check_interval: int = 5):
        """
        Args:
            max_wait_seconds: 最大等待成交时间（秒），超时后撤单
            check_interval: 检查间隔（秒）
        """
        self.max_wait_seconds = max_wait_seconds
        self.check_interval = check_interval
        
        self.orders: Dict[str, OrderInfo] = {}  # order_id -> OrderInfo
        self.orders_lock = threading.RLock()
        
        self.pending_orders = set()  # 待成交订单集合
        self.running = False
        self.check_thread = None
        
        self.on_order_filled: Optional[Callable] = None
        self.on_order_cancelled: Optional[Callable] = None
        self.on_order_timeout: Optional[Callable] = None
        
    def start(self):
        """启动订单监控线程"""
        if not self.running:
            self.running = True
            self.check_thread = threading.Thread(target=self._check_loop, daemon=True)
            self.check_thread.start()
            logger.info("订单跟踪器已启动")
    
    def stop(self):
        """停止订单监控"""
        self.running = False
        if self.check_thread:
            self.check_thread.join(timeout=5)
        logger.info("订单跟踪器已停止")
    
    def register_order(self, stock_code: str, order_id: str, volume: int,
                      price: float, order_type: str = "BUY") -> OrderInfo:
        """注册新订单"""
        with self.orders_lock:
            order = OrderInfo(stock_code, order_id, volume, price, order_type)
            self.orders[order_id] = order
            self.pending_orders.add(order_id)
            logger.info(f"订单已注册: {order_id} - {stock_code} - {volume}@{price}")
            return order
    
    def update_order_status(self, order_id: str, status: str, 
                           filled_volume: int = 0, avg_price: float = None):
        """更新订单状态（由回调调用）"""
        with self.orders_lock:
            if order_id not in self.orders:
                logger.warning(f"订单不存在: {order_id}")
                return
            
            order = self.orders[order_id]
            old_status = order.status
            order.status = status
            order.filled_volume = filled_volume
            order.last_update_time = datetime.now()
            
            if avg_price:
                order.avg_price = avg_price
            
            if status == OrderStatus.FULL:
                self.pending_orders.discard(order_id)
                logger.info(f"订单全部成交: {order_id}")
                if self.on_order_filled:
                    self.on_order_filled(order)
                    
            elif status == OrderStatus.CANCELLED:
                self.pending_orders.discard(order_id)
                logger.info(f"订单已撤单: {order_id}")
                if self.on_order_cancelled:
                    self.on_order_cancelled(order)
    
    def update_price(self, stock_code: str, current_price: float):
        """更新股票价格并记录盈利曲线"""
        with self.orders_lock:
            now = datetime.now()
            timestamp = now.timestamp()
            
            for order_id, order in self.orders.items():
                if order.stock_code == stock_code and order.status in [OrderStatus.PENDING, OrderStatus.PARTIAL]:
                    order.price_history.append((timestamp, current_price))
                    
                    if order.filled_volume > 0:
                        profit_pct = (current_price - order.avg_price) / order.avg_price * 100
                        order.profit_history.append((timestamp, profit_pct))
    
    def get_pending_orders(self) -> list:
        """获取待成交订单列表"""
        with self.orders_lock:
            return [self.orders[oid] for oid in self.pending_orders]
    
    def get_order(self, order_id: str) -> Optional[OrderInfo]:
        """获取订单信息"""
        with self.orders_lock:
            return self.orders.get(order_id)
    
    def cancel_order(self, order_id: str) -> bool:
        """取消订单"""
        with self.orders_lock:
            if order_id in self.pending_orders:
                self.pending_orders.discard(order_id)
                if order_id in self.orders:
                    self.orders[order_id].status = OrderStatus.CANCELLED
                return True
            return False
    
    def _check_loop(self):
        """检查超时订单的循环"""
        while self.running:
            try:
                self._check_pending_orders()
            except Exception as e:
                logger.error(f"检查订单时发生异常: {e}")
            
            time.sleep(self.check_interval)
    
    def _check_pending_orders(self):
        """检查待成交订单，处理超时"""
        now = datetime.now()
        
        with self.orders_lock:
            for order_id in list(self.pending_orders):
                order = self.orders.get(order_id)
                if not order:
                    continue
                
                wait_time = (now - order.order_time).total_seconds()
                
                if wait_time > self.max_wait_seconds:
                    # 只记录超时日志，不自动撤单（QMT不支持撤单）
                    logger.info(f"订单超时未成交: {order.order_id} - 股票: {order.stock_code} - 已等待{int(wait_time)}秒")
                    # 从待成交列表移除，但保留订单记录
                    self.pending_orders.discard(order_id)
                    order.status = "TIMEOUT"
    
    def get_profit_stats(self, order_id: str) -> Optional[Dict]:
        """获取订单盈利统计"""
        with self.orders_lock:
            order = self.orders.get(order_id)
            if not order or not order.profit_history:
                return None
            
            profits = [p[1] for p in order.profit_history]
            
            max_profit = max(profits)
            max_profit_time = order.profit_history[profits.index(max_profit)][0]
            
            min_profit = min(profits)
            min_profit_time = order.profit_history[profits.index(min_profit)][0]
            
            time_to_max = max_profit_time - order.order_time.timestamp()
            
            return {
                "order_id": order_id,
                "stock_code": order.stock_code,
                "max_profit_pct": max_profit,
                "max_profit_time_seconds": time_to_max,
                "min_profit_pct": min_profit,
                "order_time": order.order_time.isoformat(),
                "total_points": len(order.profit_history)
            }
    
    def get_all_profit_stats(self) -> list:
        """获取所有订单的盈利统计"""
        results = []
        with self.orders_lock:
            for order_id, order in self.orders.items():
                if order.profit_history:
                    profits = [p[1] for p in order.profit_history]
                    if profits:
                        max_profit = max(profits)
                        max_profit_time = order.profit_history[profits.index(max_profit)][0]
                        time_to_max = max_profit_time - order.order_time.timestamp()
                        
                        results.append({
                            "order_id": order_id,
                            "stock_code": order.stock_code,
                            "buy_price": order.price,
                            "filled_volume": order.filled_volume,
                            "max_profit_pct": max_profit,
                            "time_to_max_profit_seconds": time_to_max,
                            "order_time": order.order_time.isoformat(),
                            "status": order.status
                        })
        return results


class OrderCallback:
    """订单回调处理类"""
    
    def __init__(self, order_tracker: OrderTracker, trader, account):
        self.order_tracker = order_tracker
        self.trader = trader
        self.account = account
        
        order_tracker.on_order_filled = self._on_filled
        order_tracker.on_order_cancelled = self._on_cancelled
        order_tracker.on_order_timeout = self._on_timeout
    
    def _on_filled(self, order: OrderInfo):
        """成交回调"""
        logger.info(f"订单成交回调: {order.order_id}")
    
    def _on_cancelled(self, order: OrderInfo):
        """撤单回调"""
        logger.info(f"订单撤单回调: {order.order_id}")
    
    def _on_timeout(self, order: OrderInfo):
        """超时回调 - 自动撤单重排"""
        logger.warning(f"订单超时，准备撤单重排: {order.order_id}")
        
        try:
            from xtquant import xtconstant
            # 使用account的cancel_order方法
            cancel_result = self.account.cancel_order(order.order_id)
            
            if cancel_result is not None and cancel_result == 0:
                logger.info(f"撤单成功: {order.order_id}")
                order.cancel_count += 1
                
                if order.cancel_count < 3:
                    retry_result = self.trader.order_stock(
                        account=self.account,
                        stock_code=order.stock_code,
                        order_type=xtconstant.STOCK_BUY if order.order_type == "BUY" else xtconstant.STOCK_SELL,
                        order_volume=order.volume - order.filled_volume,
                        price_type=xtconstant.FIX_PRICE,
                        price=order.price,
                        strategy_name=self.account.trader_name,
                        order_remark="retry order"
                    )
                    
                    if retry_result:
                        self.order_tracker.register_order(
                            order.stock_code, 
                            str(retry_result),
                            order.volume - order.filled_volume,
                            order.price,
                            order.order_type
                        )
                        logger.info(f"重新下单成功: {retry_result}")
                else:
                    logger.warning(f"订单已重试{order.cancel_count}次，不再重试: {order.order_id}")
                    
        except Exception as e:
            logger.error(f"撤单重排失败: {e}")
