from curs.cursglobal import *
from curs.strategy import *
from typing import Dict, List
import os

class StategyLoader:
    """策略加载器"""
    def __init__(self, strategy_file_path: str, strategy_id: str = None):
        self._loader = set()
        self._strategy_file_path = strategy_file_path
        self._strategy_id = strategy_id or os.path.splitext(os.path.basename(strategy_file_path))[0]
        self._strategy = None
        pass
    @property
    def strategy_id(self):
        return self._strategy_id

    def load(self, event_bus: EventBus):
        """加载策略"""
        s_loader = FileStrategyLoader(self._strategy_file_path)
        scop = {}
        s_loader.load(scop)
        strategy_context = StrategyContext()
        self._strategy = Strategy(event_bus, scop, strategy_context)
        self._strategy.init()
         
    def unload(self, event_bus: EventBus):
        """卸载策略"""
        if self._strategy:
            self._strategy.unregister_event(event_bus)
            self._strategy = None

    @property
    def account(self):
        """获取策略的交易账户"""
        if self._strategy and hasattr(self._strategy._user_context, 'account'):
            return self._strategy._user_context.account
        return None

    def enable_live_trading(self):
        """启用实盘交易"""
        acc = self.account
        if acc and hasattr(acc, 'live_trading'):
            acc.live_trading = True
            return True
        return False

    def disable_live_trading(self):
        """禁用实盘交易（仅信号模式）"""
        acc = self.account
        if acc and hasattr(acc, 'live_trading'):
            acc.live_trading = False
            return True
        return False

    def is_live_trading_enabled(self) -> bool:
        """检查是否启用实盘"""
        acc = self.account
        if acc and hasattr(acc, 'live_trading'):
            return acc.live_trading
        return True

     
class StrategyManager:
    """策略管理器"""
    _instance = None
    _strategies: Dict[str, object] = {}  # 存储已加载策略
     
    def __new__(cls, event_bus: EventBus):
        if cls._instance is not None:
            # 确保后续调用使用相同的 event_bus
            if event_bus != cls._instance._event_bus:
                raise ValueError("StrategyManager already initialized with a different EventBus")
            return cls._instance
        # 首次创建实例
        instance = super().__new__(cls)
        instance._event_bus = event_bus
        instance._strategies = {}  # 实例变量存储策略
        cls._instance = instance
        return instance
     
    @classmethod
    def get_instance(cls):
        """获取单例实例"""
        if cls._instance is None:
            raise RuntimeError("StrategyManager has not been initialized. Please initialize it first.")
        return cls._instance
     
    def load_strategy(self, strategy_file_path: str):
        """加载策略"""
        if strategy_file_path in self._strategies:
            return self._strategies[strategy_file_path]
             
        try:
            s_loader = StategyLoader(strategy_file_path)
            s_loader.load(self._event_bus)

            # 从数据库恢复策略实盘状态
            self._apply_db_state(s_loader)

            self._strategies[strategy_file_path] = s_loader
            return s_loader
        except Exception as e:
            logger.error(f'加载策略{strategy_file_path}失败: {e}')
            raise

    def _apply_db_state(self, s_loader: StategyLoader):
        """从数据库恢复策略状态"""
        try:
            from curs.database import get_db_manager
            db = get_db_manager()
            enabled = db.get_strategy_enabled(s_loader.strategy_id)
            if not enabled:
                s_loader.disable_live_trading()
                logger.info(f"策略 {s_loader.strategy_id} 已根据配置禁用实盘")
        except Exception as e:
            logger.debug(f"恢复策略状态失败: {e}")

    def unload_strategy(self, strategy_file_path: str):
        """卸载策略"""
        if strategy_file_path in self._strategies:
            strategy_loader = self._strategies[strategy_file_path]
            strategy_loader.unload(self._event_bus)
            del self._strategies[strategy_file_path] 
            logger.info(f'策略{strategy_file_path}已卸载')
            return True
        logger.warning(f'策略{strategy_file_path}未找到，无法卸载')
        return False

    def enable_strategy(self, strategy_id: str) -> bool:
        """启用策略实盘交易"""
        for path, loader in self._strategies.items():
            if loader.strategy_id == strategy_id:
                loader.enable_live_trading()
                from curs.database import get_db_manager
                get_db_manager().set_strategy_enabled(strategy_id, True)
                logger.info(f"策略 {strategy_id} 实盘交易已开启")
                return True
        logger.warning(f"策略 {strategy_id} 未加载，无法开启实盘")
        return False

    def disable_strategy(self, strategy_id: str) -> bool:
        """禁用策略实盘交易（仅信号模式）"""
        for path, loader in self._strategies.items():
            if loader.strategy_id == strategy_id:
                loader.disable_live_trading()
                from curs.database import get_db_manager
                get_db_manager().set_strategy_enabled(strategy_id, False)
                logger.info(f"策略 {strategy_id} 实盘交易已关闭，仅保留信号")
                return True
        logger.warning(f"策略 {strategy_id} 未加载，无法关闭实盘")
        return False

    def is_strategy_enabled(self, strategy_id: str) -> bool:
        """检查策略是否启用实盘"""
        for path, loader in self._strategies.items():
            if loader.strategy_id == strategy_id:
                return loader.is_live_trading_enabled()
        return True

    def list_strategies(self) -> List[Dict]:
        """列出所有已加载策略及其状态"""
        result = []
        for path, loader in self._strategies.items():
            result.append({
                'id': loader.strategy_id,
                'path': path,
                'enabled': loader.is_live_trading_enabled(),
            })
        return result
