# coding: utf-8

import codecs
import six
import importlib
from typing import Dict
from curs.log_handler.logger import logger

class StrategyManager:
    """策略管理器"""
    _instance = None
    _strategies: Dict[str, object] = {}  # 存储已加载策略
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load_strategy(self, strategy_id: str):
        """加载策略"""
        if strategy_id in self._strategies:
            return self._strategies[strategy_id]
            
        try:
            strategy_module = importlib.import_module(f'strategies.{strategy_id}')
            strategy = strategy_module.Strategy()
            self._strategies[strategy_id] = strategy
            return strategy
        except Exception as e:
            logger.error(f'加载策略{strategy_id}失败: {e}')
            raise

    def start_strategy(self, strategy_id: str):
        """启动策略"""
        strategy = self.load_strategy(strategy_id)
        if hasattr(strategy, 'start'):
            strategy.start()
            logger.info(f'策略{strategy_id}已启动')
            return True
        return False

    def stop_strategy(self, strategy_id: str):
        """停止策略"""
        if strategy_id in self._strategies:
            strategy = self._strategies[strategy_id]
            if hasattr(strategy, 'stop'):
                strategy.stop()
                logger.info(f'策略{strategy_id}已停止')
                return True
        return False

def compile_strategy(source_code, strategy, scope):
    """编译策略代码"""
    try:
        code = compile(source_code, strategy, 'exec')
        six.exec_(code, scope)
        return scope
    except Exception as e:
        logger.error(e)

class FileStrategyLoader:
    """文件策略加载器"""
    def __init__(self, strategy_file_path):
        self._strategy_file_path = strategy_file_path

    def load(self, scope):
        """从文件加载策略"""
        with codecs.open(self._strategy_file_path, encoding="utf-8") as f:
            source_code = f.read()
        return compile_strategy(source_code, self._strategy_file_path, scope)

class SourceCodeStrategyLoader:
    """源代码策略加载器"""
    def __init__(self, code):
        self._code = code

    def load(self, scope):
        """从源代码加载策略"""
        return compile_strategy(self._code, "strategy.py", scope)

class UserFuncStrategyLoader:
    """用户函数策略加载器"""
    def __init__(self, user_funcs):
        self._user_funcs = user_funcs

    def load(self, scope):
        """从用户函数加载策略"""
        return self._user_funcs

def main():
    """测试策略加载"""
    s_loader = FileStrategyLoader("./test_strategy.py")
    scop = {}
    s_loader.load(scop)
    print(scop.keys())

if __name__ == "__main__":
    main()
