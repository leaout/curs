# coding: utf-8
import unittest
import time
import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from croniter import croniter


class TestScheduledTask(unittest.TestCase):
    """测试定时任务类"""

    def test_create_task(self):
        """测试创建任务"""
        from curs.utils.task_scheduler import ScheduledTask
        
        task = ScheduledTask(
            id=1,
            name="测试任务",
            task_type="test",
            cron_expression="0 * * * *",
            is_enabled=True,
            config={'key': 'value'}
        )
        
        self.assertEqual(task.id, 1)
        self.assertEqual(task.name, "测试任务")
        self.assertEqual(task.task_type, "test")
        self.assertEqual(task.cron_expression, "0 * * * *")
        self.assertTrue(task.is_enabled)
        self.assertEqual(task.config, {'key': 'value'})

    def test_task_from_dict(self):
        """测试从字典创建任务"""
        from curs.utils.task_scheduler import ScheduledTask
        
        data = {
            'id': 1,
            'name': '测试任务',
            'task_type': 'test',
            'cron_expression': '0 * * * *',
            'interval_seconds': None,
            'is_enabled': True,
            'config': json.dumps({'key': 'value'}),
            'last_run_at': None,
            'next_run_at': None,
            'run_count': 0,
            'success_count': 0,
            'fail_count': 0
        }
        
        task = ScheduledTask.from_dict(data)
        
        self.assertEqual(task.id, 1)
        self.assertEqual(task.name, '测试任务')
        self.assertEqual(task.config, {'key': 'value'})

    def test_task_to_dict(self):
        """测试任务转字典"""
        from curs.utils.task_scheduler import ScheduledTask
        
        task = ScheduledTask(
            id=1,
            name="测试任务",
            task_type="test",
            cron_expression="0 * * * *",
            is_enabled=True,
            config={'key': 'value'}
        )
        
        task_dict = task.to_dict()
        
        self.assertEqual(task_dict['id'], 1)
        self.assertEqual(task_dict['name'], '测试任务')
        self.assertEqual(task_dict['task_type'], 'test')

    def test_record_success(self):
        """测试记录成功"""
        from curs.utils.task_scheduler import ScheduledTask
        
        task = ScheduledTask(id=1, name="测试", task_type="test")
        task.record_success()
        
        self.assertEqual(task.run_count, 1)
        self.assertEqual(task.success_count, 1)
        self.assertEqual(task.fail_count, 0)

    def test_record_fail(self):
        """测试记录失败"""
        from curs.utils.task_scheduler import ScheduledTask
        
        task = ScheduledTask(id=1, name="测试", task_type="test")
        task.record_fail()
        
        self.assertEqual(task.run_count, 1)
        self.assertEqual(task.success_count, 0)
        self.assertEqual(task.fail_count, 1)

    def test_should_run_disabled(self):
        """测试禁用任务不应运行"""
        from curs.utils.task_scheduler import ScheduledTask
        
        task = ScheduledTask(
            id=1,
            name="测试",
            task_type="test",
            is_enabled=False
        )
        
        self.assertFalse(task.should_run(datetime.now()))

    def test_should_run_cron(self):
        """测试cron表达式触发"""
        from curs.utils.task_scheduler import ScheduledTask
        
        task = ScheduledTask(
            id=1,
            name="测试",
            task_type="test",
            cron_expression="* * * * *",
            is_enabled=True
        )
        
        now = datetime.now()
        result = task.should_run(now)
        
        self.assertTrue(result)

    def test_should_run_interval(self):
        """测试间隔触发"""
        from curs.utils.task_scheduler import ScheduledTask
        
        task = ScheduledTask(
            id=1,
            name="测试",
            task_type="test",
            interval_seconds=60,
            is_enabled=True
        )
        task.last_run_at = datetime.now() - timedelta(seconds=120)
        
        self.assertTrue(task.should_run(datetime.now()))

    def test_should_run_interval_not_yet(self):
        """测试间隔未到不触发"""
        from curs.utils.task_scheduler import ScheduledTask
        
        task = ScheduledTask(
            id=1,
            name="测试",
            task_type="test",
            interval_seconds=60,
            is_enabled=True
        )
        task.last_run_at = datetime.now() - timedelta(seconds=30)
        
        self.assertFalse(task.should_run(datetime.now()))


class TestTaskScheduler(unittest.TestCase):
    """测试任务调度器"""

    def setUp(self):
        self.scheduler_class = None
        self.scheduler_instance = None

    def tearDown(self):
        if self.scheduler_instance:
            self.scheduler_instance.stop()

    def test_singleton(self):
        """测试单例模式"""
        from curs.utils.task_scheduler import TaskScheduler
        
        scheduler1 = TaskScheduler.get_instance()
        scheduler2 = TaskScheduler.get_instance()
        
        self.assertIs(scheduler1, scheduler2)

    def test_register_callback(self):
        """测试注册回调"""
        from curs.utils.task_scheduler import TaskScheduler
        
        scheduler = TaskScheduler.get_instance()
        
        def dummy_callback(config):
            return "test"
        
        scheduler.register_callback('test_type', dummy_callback)
        
        self.assertIn('test_type', scheduler._callbacks)
        self.assertEqual(scheduler._callbacks['test_type'], dummy_callback)

    def test_add_task(self):
        """测试添加任务"""
        from curs.utils.task_scheduler import TaskScheduler, ScheduledTask
        
        scheduler = TaskScheduler.get_instance()
        task = ScheduledTask(
            id=999,
            name="测试任务",
            task_type="test"
        )
        
        scheduler.add_task(task)
        
        self.assertEqual(scheduler.get_task(999), task)

    def test_remove_task(self):
        """测试移除任务"""
        from curs.utils.task_scheduler import TaskScheduler, ScheduledTask
        
        scheduler = TaskScheduler.get_instance()
        task = ScheduledTask(
            id=999,
            name="测试任务",
            task_type="test"
        )
        
        scheduler.add_task(task)
        scheduler.remove_task(999)
        
        self.assertIsNone(scheduler.get_task(999))

    def test_get_all_tasks(self):
        """测试获取所有任务"""
        from curs.utils.task_scheduler import TaskScheduler, ScheduledTask
        
        scheduler = TaskScheduler.get_instance()
        scheduler._tasks.clear()
        
        task1 = ScheduledTask(id=1, name="任务1", task_type="test")
        task2 = ScheduledTask(id=2, name="任务2", task_type="test")
        
        scheduler.add_task(task1)
        scheduler.add_task(task2)
        
        tasks = scheduler.get_all_tasks()
        
        self.assertEqual(len(tasks), 2)


class TestStartStopScheduler(unittest.TestCase):
    """测试调度器启动停止函数"""

    @patch('curs.utils.task_scheduler.TaskScheduler')
    def test_start_scheduler(self, mock_scheduler_class):
        """测试启动调度器"""
        from curs.utils.task_scheduler import start_scheduler
        
        mock_instance = MagicMock()
        mock_scheduler_class.get_instance.return_value = mock_instance
        
        start_scheduler()
        
        mock_instance.load_tasks_from_db.assert_called_once()
        mock_instance.start.assert_called_once()

    @patch('curs.utils.task_scheduler.TaskScheduler')
    def test_stop_scheduler(self, mock_scheduler_class):
        """测试停止调度器"""
        from curs.utils.task_scheduler import stop_scheduler
        
        mock_instance = MagicMock()
        mock_scheduler_class.get_instance.return_value = mock_instance
        
        stop_scheduler()
        
        mock_instance.stop.assert_called_once()


if __name__ == '__main__':
    unittest.main()