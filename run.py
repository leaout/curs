# coding: utf-8
"""
Curs - 量化投资平台启动入口

Usage:
    python run.py                    # 启动所有服务
    python run.py --web-only          # 仅启动Web服务
    python run.py --engine-only       # 仅启动交易引擎
    python run.py -p 8080             # 指定Web端口
    python run.py --help              # 查看帮助
"""

import os
import sys
import signal
import argparse
import logging
import threading
import time
import subprocess
from functools import wraps

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_and_start_qmt(config):
    """通过QMT账户连接成功作为判断，如果连接不上则启动QMT"""
    try:
        from curs.broker.qmt_account import QmtStockAccount

        qmt_path = config["qmt"]["path"]
        qmt_account_id = config["qmt"]["account_id"]
        qmt_trader_name = config["qmt"]["trader_name"]

        connection_success = QmtStockAccount.test_connection(
            path=qmt_path,
            account_id=qmt_account_id,
            trader_name=qmt_trader_name,
            session_id=int(time.time())
        )

        if connection_success:
            logger.info("QMT账户连接成功")
            return True

        logger.warning("QMT账户连接失败，尝试启动QMT...")

        # 使用 E:\script\startqmt.bat 启动QMT（不阻塞）
        startqmt_path = r"E:\script\startqmt.bat"
        if os.path.exists(startqmt_path):
            logger.info(f"执行 {startqmt_path}")
            subprocess.Popen(
                ["cmd", "/c", "start", "QMT", startqmt_path],
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        else:
            logger.warning(f"未找到 {startqmt_path}，尝试直接启动QMT")
            qmt_exe = os.path.join(qmt_path, "bin.x64", "startminiqmt.bat")
            if os.path.exists(qmt_exe):
                subprocess.Popen(
                    ["cmd", "/c", "start", "QMT", qmt_exe],
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )

        # 等待QMT启动
        max_checks = 6
        for i in range(max_checks):
            logger.info(f"等待QMT启动 ({i+1}/{max_checks})...")
            time.sleep(10)
            retry = QmtStockAccount.test_connection(
                path=qmt_path,
                account_id=qmt_account_id,
                trader_name=qmt_trader_name,
                session_id=int(time.time()) + i
            )
            if retry:
                logger.info("QMT账户连接成功")
                return True

        logger.error("QMT连接失败，将继续运行但交易可能不可用")
        return False

    except Exception as e:
        logger.exception(f"QMT连接检查时出错: {e}")
        return False


def singleton(cls):
    instances = {}
    @wraps(cls)
    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]
    return get_instance


class CursApp:
    """Curs应用主类"""
    
    def __init__(self, web_port=5000, engine_port=5001):
        self.web_port = web_port
        self.engine_port = engine_port
        self.web_app = None
        self.engine = None
        self.running = False
        self.threads = []
    
    def load_config(self):
        """加载配置"""
        from curs.utils.config import load_yaml
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_file_path = os.path.join(current_dir, "config.yml")
        config = load_yaml(config_file_path)
        logger.info(f"配置文件: {config_file_path}")
        return config
    
    def init_web(self):
        """初始化Web服务"""
        from flask import Flask
        from web.app import create_app
        
        self.web_app = create_app()
        
        # 初始化数据库表
        from curs.database import init_db
        init_db()
        
        # 自动导入 GitHub Actions 采集的数据
        self._import_collected_data()
        
        logger.info(f"Web服务已初始化，端口: {self.web_port}")
    
    def _import_collected_data(self):
        """导入 GitHub Actions 采集的热点股票数据到数据库"""
        try:
            from data_collection.import_from_collected import main as do_import
            result = do_import()
            logger.info(f"数据导入: {result}")
        except Exception as e:
            logger.debug(f"未导入采集数据（首次运行或无数据文件）: {e}")
    
    def init_engine(self):
        """初始化交易引擎"""
        config = self.load_config()
        
        from curs.core.engine import Engine
        from curs.cursglobal import CursGlobal
        from curs.events import EventBus
        
        event_bus = EventBus()
        event_bus.start()
        
        global_instance = CursGlobal(event_bus, config)
        self.engine = Engine(event_bus, global_instance)
        
        # 加载策略
        strategy_path = config.get('strategy', {}).get('path', './strategies')
        self._load_strategies(strategy_path, event_bus)
        
        logger.info("交易引擎已初始化")
    
    def _load_strategies(self, strategy_path, event_bus):
        """加载策略"""
        from curs.strategy_manager import StrategyManager
        manager = StrategyManager(event_bus)
        
        if not os.path.exists(strategy_path):
            logger.warning(f"策略目录不存在: {strategy_path}")
            return
        
        for root, dirs, files in os.walk(strategy_path):
            for file in files:
                if file.endswith(".py") and file != "__init__.py":
                    strategy_file = os.path.join(root, file)
                    try:
                        manager.load_strategy(strategy_file)
                        logger.info(f"加载策略: {file}")
                    except Exception as e:
                        logger.error(f"加载策略失败 {file}: {e}")
    
    def start_web(self):
        """启动Web服务"""
        if self.web_app:
            self.web_app.run(
                host='0.0.0.0',
                port=self.web_port,
                debug=False,
                use_reloader=False
            )
    
    def start_engine(self):
        """启动交易引擎"""
        if self.engine:
            self.engine.start()
            logger.info("交易引擎已启动")
            
            # 保持运行
            while self.running:
                time.sleep(3)
    
    def start(self, web=True, engine=True):
        """启动所有或部分服务"""
        self.running = True
        
        # 创建数据目录
        os.makedirs('data/strategy_records', exist_ok=True)
        
        if web:
            self.init_web()
            web_thread = threading.Thread(target=self.start_web, daemon=True)
            web_thread.start()
            self.threads.append(web_thread)
            logger.info(f"Web服务已启动: http://localhost:{self.web_port}")
        
        if engine:
            # 检查并启动QMT
            config = self.load_config()
            if not check_and_start_qmt(config):
                logger.warning("QMT未连接，交易功能将不可用")
            
            self.init_engine()
            engine_thread = threading.Thread(target=self.start_engine, daemon=True)
            engine_thread.start()
            self.threads.append(engine_thread)
            logger.info(f"交易引擎已启动，API端口: {self.engine_port}")
        
        # 等待信号退出
        def signal_handler(sig, frame):
            logger.info("收到退出信号，正在关闭...")
            self.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        logger.info("Curs 量化平台已启动")
        logger.info("按 Ctrl+C 退出")
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()
    
    def stop(self):
        """停止所有服务"""
        self.running = False
        if self.engine:
            self.engine.stop()
        logger.info("所有服务已停止")


def create_parser():
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description='Curs 量化投资平台',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run.py                       启动所有服务
  python run.py --web-only            仅启动Web服务
  python run.py --engine-only         仅启动交易引擎
  python run.py -p 8080               指定Web端口
  python run.py --no-web              不启动Web服务
  python run.py --import-data         仅导入GH Actions采集数据
        """
    )
    
    parser.add_argument(
        '-p', '--port',
        type=int,
        default=5000,
        help='Web服务端口 (默认: 5000)'
    )
    
    parser.add_argument(
        '--web-only',
        action='store_true',
        help='仅启动Web服务'
    )
    
    parser.add_argument(
        '--engine-only',
        action='store_true',
        help='仅启动交易引擎'
    )
    
    parser.add_argument(
        '--no-web',
        action='store_true',
        help='不启动Web服务'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='显示详细日志'
    )
    
    parser.add_argument(
        '--import-data',
        action='store_true',
        help='仅导入GitHub Actions采集数据，不启动服务'
    )
    
    return parser


def main():
    parser = create_parser()
    args = parser.parse_args()
    
    # 设置日志级别
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 仅导入数据模式
    if args.import_data:
        from curs.database import init_db
        init_db()
        from data_collection.import_from_collected import main as do_import
        result = do_import()
        print(result)
        return
    
    # 确定启动模式
    web = not args.engine_only
    engine = not args.web_only
    
    if args.no_web:
        web = False
    
    # 创建并启动应用
    app = CursApp(web_port=args.port)
    app.start(web=web, engine=engine)


if __name__ == "__main__":
    main()
