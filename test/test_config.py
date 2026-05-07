# coding: utf-8
import unittest
import os
import tempfile
import yaml
from unittest.mock import patch, MagicMock


class TestLoadYaml(unittest.TestCase):
    """测试配置加载功能"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "test_config.yml")
        self.local_config_file = os.path.join(self.temp_dir, "test_config.local.yml")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_load_basic_config(self):
        """测试基本配置加载"""
        config_data = {
            'database': {'host': 'localhost', 'port': 5432},
            'qmt': {'path': '/path/to/qmt'}
        }
        with open(self.config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f)

        from curs.utils.config import load_yaml
        config = load_yaml(self.config_file)

        self.assertEqual(config['database']['host'], 'localhost')
        self.assertEqual(config['database']['port'], 5432)
        self.assertEqual(config['qmt']['path'], '/path/to/qmt')

    def test_load_local_config_override(self):
        """测试本地配置覆盖"""
        base_config = {'database': {'host': 'localhost', 'port': 5432}}
        local_config = {'database': {'port': 5433}}

        with open(self.config_file, 'w', encoding='utf-8') as f:
            yaml.dump(base_config, f)
        with open(self.local_config_file, 'w', encoding='utf-8') as f:
            yaml.dump(local_config, f)

        from curs.utils.config import load_yaml
        config = load_yaml(self.config_file)

        self.assertEqual(config['database']['host'], 'localhost')
        self.assertEqual(config['database']['port'], 5433)

    def test_env_override_database(self):
        """测试数据库环境变量覆盖"""
        config_data = {'database': {'host': 'localhost', 'port': 5432}}

        with open(self.config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f)

        with patch.dict(os.environ, {
            'CURS_DB_HOST': 'remotehost',
            'CURS_DB_PORT': '5433'
        }):
            from curs.utils.config import load_yaml
            config = load_yaml(self.config_file)

            self.assertEqual(config['database']['host'], 'remotehost')
            self.assertEqual(config['database']['port'], '5433')

    def test_env_override_qmt(self):
        """测试QMT环境变量覆盖"""
        config_data = {'qmt': {'path': '/default/path', 'account_id': '123'}}

        with open(self.config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f)

        with patch.dict(os.environ, {
            'CURS_QMT_PATH': '/custom/path',
            'CURS_QMT_ACCOUNT_ID': '456'
        }):
            from curs.utils.config import load_yaml
            config = load_yaml(self.config_file)

            self.assertEqual(config['qmt']['path'], '/custom/path')
            self.assertEqual(config['qmt']['account_id'], '456')


class TestMergeConfig(unittest.TestCase):
    """测试配置合并功能"""

    def test_merge_nested_dict(self):
        """测试嵌套字典合并"""
        from curs.utils.config import _merge_config

        base = {'a': 1, 'b': {'c': 2, 'd': 3}}
        override = {'b': {'c': 20, 'e': 4}}

        _merge_config(base, override)

        self.assertEqual(base['a'], 1)
        self.assertEqual(base['b']['c'], 20)
        self.assertEqual(base['b']['d'], 3)
        self.assertEqual(base['b']['e'], 4)


if __name__ == '__main__':
    unittest.main()