# coding: utf-8

import codecs
import six
from curs.log_handler.logger import logger

def compile_strategy(source_code, strategy, scope):
    try:
        code = compile(source_code, strategy, 'exec')
        six.exec_(code, scope)
        return scope
    except Exception as e:
        logger.error(e)



class FileStrategyLoader():
    def __init__(self, strategy_file_path):
        self._strategy_file_path = strategy_file_path

    def load(self, scope):
        with codecs.open(self._strategy_file_path, encoding="utf-8") as f:
            source_code = f.read()

        return compile_strategy(source_code, self._strategy_file_path, scope)


class SourceCodeStrategyLoader():
    def __init__(self, code):
        self._code = code

    def load(self, scope):
        return compile_strategy(self._code, "strategy.py", scope)


class UserFuncStrategyLoader():
    def __init__(self, user_funcs):
        self._user_funcs = user_funcs

    def load(self, scope):
        return self._user_funcs