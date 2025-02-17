from curs.cursglobal import *
from curs.strategy import *
from typing import Dict

class StategyLoader:
    """策略加载器"""
    def __init__(self, strategy_file_path: str):
        self._loader = set()
        self._strategy_file_path = strategy_file_path
        self._strategy = None
        pass
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
            self._strategy.unregister_event()
            self._strategy = None
        
    
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

            self._strategies[strategy_file_path] = s_loader
            return s_loader
        except Exception as e:
            logger.error(f'加载策略{strategy_file_path}失败: {e}')
            raise
    def unload_strategy(self, strategy_file_path: str):
        """重新加载策略"""
        if strategy_file_path in self._strategies:
            strategy_loader = self._strategies[strategy_file_path]
            strategy_loader.unload(self._event_bus)
            del self._strategies[strategy_file_path] 
            logger.info(f'策略{strategy_file_path}已卸载')
            return True
        logger.warning(f'策略{strategy_file_path}未找到，无法卸载')
        return False
    