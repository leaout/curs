# coding: utf-8

import codecs
import six
from curs.log_handler.logger import logger

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
