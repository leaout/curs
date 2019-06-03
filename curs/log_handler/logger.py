# coding: utf-8

import logging
import logging.handlers

class curse_logger(object):
    """Log对象
    :param log_path: log文件名路径
    """
    def __init__(self,log_path='default.log'):
        self._logger = logging.getLogger()
        self._logger.setLevel(logging.DEBUG)
        file_print = logging.handlers.TimedRotatingFileHandler(log_path, 'D')
        std_print = logging.StreamHandler()
        fmt = logging.Formatter("%(asctime)s %(pathname)s %(filename)s %(funcName)s %(lineno)d %(levelname)s - %(message)s","%Y-%m-%d %H:%M:%S")
        std_print.setFormatter(fmt)
        file_print.setFormatter(fmt)
        self._logger.addHandler(file_print)
        self._logger.addHandler(std_print)

        self.debug = self._logger.debug
        self.info = self._logger.info
        self.warning = self._logger.warning
        self.error = self._logger.error

    # def debug(self,stream):
    #     self.logger.debug(stream)
    # def info(self,stream):
    #     self.logger.info(stream)
    # def warning(self,stream):
    #     self.logger.warning(stream)
    # def error(self,stream):
    #     self.logger.error(stream)
    # debug = logger.debug
    # info = logger.info
    # warning = logger.warning
    # error = logger.error




logger = curse_logger()


# logger.info("this is info log")
# logger.debug("this is debug log")
# logger.warning("this is warning log")
# logger.error("this is error log")