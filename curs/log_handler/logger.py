# coding: utf-8

import logging
import logging.handlers
import sys
import time

class curs_logger(object):
    """Log对象
    :param log_path: log文件名路径
    """
    def __init__(self,log_path='default.log'):
        self._logger = logging.getLogger()
        self._logger.setLevel(logging.DEBUG)
        file_print = logging.handlers.TimedRotatingFileHandler(log_path, 'D', 
            encoding='utf-8'  # 指定编码
            )
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

def progress_bar(total,count,msg=""):
    """
    进度条效果
    """
    process = count / total *100
    # 获取标准输出
    _output = sys.stdout
    # 通过参数决定你的进度条总量是多少

    # 输出进度条
    _output.write('\r'+msg+ 'complete percent:%.1f '%process)
    # 将标准输出一次性刷新
    _output.flush()




logger = curs_logger()


# logger.info("this is info log")
# logger.debug("this is debug log")
# logger.warning("this is warning log")
# logger.error("this is error log")
def main():
    total  =100
    for count in range(0,101):
        time.sleep(0.1)
        progress_bar(total,count)
    pass

if __name__ == "__main__":
    main()