# coding: utf-8
import threading
import time
import json
import logging
import importlib
from datetime import datetime
from typing import Dict, List, Optional, Callable
from croniter import croniter
import schedule

logger = logging.getLogger(__name__)

class TaskScheduler:
    """定时任务调度器"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __init__(self):
        self._tasks: Dict[int, 'ScheduledTask'] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._callbacks: Dict[str, Callable] = {}
    
    @classmethod
    def get_instance(cls) -> 'TaskScheduler':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    def register_callback(self, task_type: str, callback: Callable):
        """注册任务类型回调"""
        self._callbacks[task_type] = callback
        logger.info(f"注册任务回调: {task_type}")
    
    def start(self):
        """启动调度器"""
        if self._running:
            logger.warning("调度器已在运行中")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("任务调度器已启动")
    
    def stop(self):
        """停止调度器"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("任务调度器已停止")
    
    def _run_loop(self):
        """调度器主循环"""
        while self._running:
            self._check_and_run_tasks()
            time.sleep(1)
    
    def _check_and_run_tasks(self):
        """检查并执行到期的任务"""
        now = datetime.now()
        
        for task_id, task in list(self._tasks.items()):
            if not task.is_enabled:
                continue
            
            if task.should_run(now):
                logger.info(f"执行任务: {task.name} (ID: {task_id})")
                self._execute_task(task_id, task)
    
    def _execute_task(self, task_id: int, task: 'ScheduledTask'):
        """执行单个任务"""
        from curs.database import get_db_manager
        db = get_db_manager()
        
        start_time = datetime.now()
        status = 'SUCCESS'
        message = ''
        error_detail = None
        
        try:
            callback = self._callbacks.get(task.task_type)
            if callback:
                result = callback(task.config)
                message = f"执行成功: {result}"
            else:
                message = f"未找到任务类型处理器: {task.task_type}"
            
            task.record_success()
        except Exception as e:
            status = 'FAILED'
            error_detail = str(e)
            message = f"执行失败: {e}"
            task.record_fail()
            logger.exception(f"任务执行失败: {task.name}")
        
        duration = (datetime.now() - start_time).total_seconds()
        
        task.update_run_info(start_time, duration)
        
        db.log_task_execution(task_id, status, message, start_time, datetime.now(), duration, error_detail)
    
    def load_tasks_from_db(self):
        """从数据库加载任务"""
        from curs.database import get_db_manager
        db = get_db_manager()
        
        tasks = db.get_all_scheduled_tasks()
        self._tasks.clear()
        
        for task_data in tasks:
            task = ScheduledTask.from_dict(task_data)
            self._tasks[task.id] = task
            logger.info(f"加载任务: {task.name} (ID: {task.id})")
    
    def add_task(self, task: 'ScheduledTask'):
        """添加任务"""
        self._tasks[task.id] = task
    
    def remove_task(self, task_id: int):
        """移除任务"""
        if task_id in self._tasks:
            del self._tasks[task_id]
    
    def get_task(self, task_id: int) -> Optional['ScheduledTask']:
        """获取任务"""
        return self._tasks.get(task_id)
    
    def get_all_tasks(self) -> List['ScheduledTask']:
        """获取所有任务"""
        return list(self._tasks.values())


class ScheduledTask:
    """定时任务"""
    
    def __init__(self, id: int, name: str, task_type: str, 
                 cron_expression: str = None, interval_seconds: int = None,
                 is_enabled: bool = True, config: dict = None):
        self.id = id
        self.name = name
        self.task_type = task_type
        self.cron_expression = cron_expression
        self.interval_seconds = interval_seconds
        self.is_enabled = is_enabled
        self.config = config or {}
        
        self.last_run_at: Optional[datetime] = None
        self.next_run_at: Optional[datetime] = None
        self.run_count = 0
        self.success_count = 0
        self.fail_count = 0
        
        self._cron = None
        if cron_expression:
            try:
                self._cron = croniter(cron_expression)
            except Exception:
                logger.warning(f"无效的cron表达式: {cron_expression}")
    
    def should_run(self, now: datetime) -> bool:
        """判断任务是否应该执行"""
        if not self.is_enabled:
            return False
        
        if self._cron:
            prev = self._cron.get_prev(datetime)
            if self.last_run_at:
                if prev > self.last_run_at:
                    self._cron = croniter(self.cron_expression, now)
                    self.next_run_at = self._cron.get_next(datetime)
                    return True
            else:
                self._cron = croniter(self.cron_expression, now)
                self.next_run_at = self._cron.get_next(datetime)
                return True
            return False
        
        if self.interval_seconds and self.last_run_at:
            elapsed = (now - self.last_run_at).total_seconds()
            if elapsed >= self.interval_seconds:
                self.next_run_at = now + type(self.interval_seconds)()
                return True
        
        return False
    
    def record_success(self):
        """记录成功执行"""
        self.run_count += 1
        self.success_count += 1
    
    def record_fail(self):
        """记录失败"""
        self.run_count += 1
        self.fail_count += 1
    
    def update_run_info(self, start_time: datetime, duration: float):
        """更新运行信息"""
        self.last_run_at = start_time
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ScheduledTask':
        """从字典创建任务"""
        config = data.get('config')
        if isinstance(config, str):
            config = json.loads(config)
        
        task = cls(
            id=data.get('id', 0),
            name=data.get('name', ''),
            task_type=data.get('task_type', ''),
            cron_expression=data.get('cron_expression'),
            interval_seconds=data.get('interval_seconds'),
            is_enabled=data.get('is_enabled', True),
            config=config
        )
        task.last_run_at = data.get('last_run_at')
        task.next_run_at = data.get('next_run_at')
        task.run_count = data.get('run_count', 0)
        task.success_count = data.get('success_count', 0)
        task.fail_count = data.get('fail_count', 0)
        
        return task
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'id': self.id,
            'name': self.name,
            'task_type': self.task_type,
            'cron_expression': self.cron_expression,
            'interval_seconds': self.interval_seconds,
            'is_enabled': self.is_enabled,
            'config': self.config,
            'last_run_at': self.last_run_at.isoformat() if self.last_run_at else None,
            'next_run_at': self.next_run_at.isoformat() if self.next_run_at else None,
            'run_count': self.run_count,
            'success_count': self.success_count,
            'fail_count': self.fail_count
        }


def start_scheduler():
    """启动任务调度器"""
    scheduler = TaskScheduler.get_instance()
    scheduler.load_tasks_from_db()
    scheduler.start()
    logger.info("任务调度器已启动")


def stop_scheduler():
    """停止任务调度器"""
    scheduler = TaskScheduler.get_instance()
    scheduler.stop()
