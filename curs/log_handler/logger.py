# coding: utf-8

import logging
import logging.handlers
import sys
import time
import os

class curs_logger(object):
    """Log对象
    :param log_path: log文件名路径
    """
    def __init__(self, log_path='logs/default.log', backup_count=5):
        self._logger = logging.getLogger()
        self._logger.setLevel(logging.INFO)
        
        # 确保日志目录存在
        log_dir = os.path.dirname(log_path)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        # 按天轮转，保留5个文件
        file_print = logging.handlers.TimedRotatingFileHandler(
            log_path, 
            when='D',
            interval=1,
            backupCount=backup_count,
            encoding='utf-8'
        )
        
        # 简化格式
        fmt = logging.Formatter(
            "%(asctime)s %(levelname)s - %(message)s",
            "%Y-%m-%d %H:%M:%S"
        )
        
        std_print = logging.StreamHandler()
        std_print.setFormatter(fmt)
        file_print.setFormatter(fmt)
        
        self._logger.addHandler(file_print)
        self._logger.addHandler(std_print)

        self.debug = self._logger.debug
        self.info = self._logger.info
        self.warning = self._logger.warning
        self.error = self._logger.error

def progress_bar(total, count, msg=""):
    """进度条效果"""
    process = count / total * 100
    _output = sys.stdout
    _output.write('\r' + msg + 'complete percent:%.1f ' % process)
    _output.flush()


# 默认日志实例
logger = curs_logger(log_path='logs/default.log', backup_count=5)