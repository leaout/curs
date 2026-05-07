# coding: utf-8
import unittest
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock


class TestExecuteDynamicTask(unittest.TestCase):
    """测试动态任务执行"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.test_script = os.path.join(self.temp_dir, "test_script.py")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_test_script(self, script_content):
        with open(self.test_script, 'w', encoding='utf-8') as f:
            f.write(script_content)

    def test_missing_script_path(self):
        """测试缺少script_path"""
        from curs.utils.task_callbacks import execute_dynamic_task
        
        result = execute_dynamic_task({'function_name': 'test_func'})
        
        self.assertIn("错误", result)
        self.assertIn("script_path", result)

    def test_missing_function_name(self):
        """测试缺少function_name"""
        from curs.utils.task_callbacks import execute_dynamic_task
        
        result = execute_dynamic_task({'script_path': '/some/path.py'})
        
        self.assertIn("错误", result)
        self.assertIn("function_name", result)

    def test_script_not_exists(self):
        """测试脚本文件不存在"""
        from curs.utils.task_callbacks import execute_dynamic_task
        
        result = execute_dynamic_task({
            'script_path': '/nonexistent/script.py',
            'function_name': 'test_func'
        })
        
        self.assertIn("错误", result)
        self.assertIn("不存在", result)

    def test_function_not_exists(self):
        """测试函数不存在"""
        self._create_test_script("def some_other_func():\n    pass\n")
        
        from curs.utils.task_callbacks import execute_dynamic_task
        
        result = execute_dynamic_task({
            'script_path': self.test_script,
            'function_name': 'test_func'
        })
        
        self.assertIn("错误", result)
        self.assertIn("不存在", result)

    def test_execute_success(self):
        """测试成功执行"""
        self._create_test_script("""
def test_func(config):
    return "success"
""")
        
        from curs.utils.task_callbacks import execute_dynamic_task
        
        result = execute_dynamic_task({
            'script_path': self.test_script,
            'function_name': 'test_func'
        })
        
        self.assertIn("执行成功", result)


class TestTaskCallbacks(unittest.TestCase):
    """测试任务回调函数"""

    @patch('curs.utils.task_callbacks.execute_dynamic_task')
    def test_task_sync_hot_stocks(self, mock_execute):
        """测试同步热点股票任务"""
        from curs.utils.task_callbacks import task_sync_hot_stocks
        
        mock_execute.return_value = "执行成功"
        
        result = task_sync_hot_stocks({})
        
        mock_execute.assert_called_once()
        args = mock_execute.call_args[0][0]
        self.assertIn('hot_stocks.py', args['script_path'])

    @patch('curs.utils.task_callbacks.execute_dynamic_task')
    def test_task_collect_hot_stocks(self, mock_execute):
        """测试采集热点股票任务"""
        from curs.utils.task_callbacks import task_collect_hot_stocks
        
        mock_execute.return_value = "执行成功"
        
        result = task_collect_hot_stocks({})
        
        mock_execute.assert_called_once()
        args = mock_execute.call_args[0][0]
        self.assertIn('eastmoney_hot_stocks.py', args['script_path'])


class TestRegisterAllTasks(unittest.TestCase):
    """测试任务注册"""

    def test_register_all_tasks(self):
        """测试注册所有任务"""
        from curs.utils.task_callbacks import register_all_tasks
        
        mock_scheduler = MagicMock()
        
        register_all_tasks(mock_scheduler)
        
        self.assertEqual(mock_scheduler.register_callback.call_count, 7)
        
        registered_types = [
            call[0][0] for call in mock_scheduler.register_callback.call_args_list
        ]
        
        self.assertIn('sync_hot_stocks', registered_types)
        self.assertIn('collect_hot_stocks', registered_types)
        self.assertIn('sync_stock_info', registered_types)
        self.assertIn('profit_analysis', registered_types)
        self.assertIn('clear_hot_stocks', registered_types)
        self.assertIn('custom_script', registered_types)
        self.assertIn('custom', registered_types)


if __name__ == '__main__':
    unittest.main()