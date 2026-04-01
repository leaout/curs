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
from functools import wraps

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


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
        logger.info(f"Web服务已初始化，端口: {self.web_port}")
    
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
        self._load_strategies(strategy_path)
        
        logger.info("交易引擎已初始化")
    
    def _load_strategies(self, strategy_path):
        """加载策略"""
        from curs.strategy_manager import StrategyManager
        manager = StrategyManager.get_instance()
        
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
        
        if web:
            self.init_web()
            web_thread = threading.Thread(target=self.start_web, daemon=True)
            web_thread.start()
            self.threads.append(web_thread)
            logger.info(f"Web服务已启动: http://localhost:{self.web_port}")
        
        if engine:
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
  python run.py                    启动所有服务
  python run.py --web-only         仅启动Web服务
  python run.py --engine-only      仅启动交易引擎
  python run.py -p 8080            指定Web端口
  python run.py --no-web           不启动Web服务
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
    
    return parser


def main():
    parser = create_parser()
    args = parser.parse_args()
    
    # 设置日志级别
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
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
