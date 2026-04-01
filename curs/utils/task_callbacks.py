# coding: utf-8
"""
定时任务回调函数模块
动态任务执行器 - 根据配置执行指定的脚本函数
"""
import logging
import sys
import os
import importlib.util

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


def execute_dynamic_task(config: dict) -> str:
    """
    动态执行任务
    根据config中的script_path和function_name动态加载执行
    """
    script_path = config.get('script_path')
    function_name = config.get('function_name')
    
    if not script_path or not function_name:
        return "错误: 缺少script_path或function_name配置"
    
    # 处理相对路径
    if not os.path.isabs(script_path):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        script_path = os.path.join(base_dir, script_path)
    
    if not os.path.exists(script_path):
        return f"错误: 脚本文件不存在: {script_path}"
    
    try:
        # 动态加载模块
        module_name = f"task_module_{os.path.basename(script_path)}"
        spec = importlib.util.spec_from_file_location(module_name, script_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # 调用指定函数
        if hasattr(module, function_name):
            func = getattr(module, function_name)
            result = func(config)
            return f"执行成功: {result}"
        else:
            return f"错误: 函数 {function_name} 不存在于脚本中"
            
    except Exception as e:
        logger.exception(f"动态任务执行失败: {script_path}.{function_name}")
        return f"执行失败: {e}"


# ==================== 内置任务处理器 ====================
# 这些是简化版，用于兼容旧的简单任务类型

def task_sync_hot_stocks(config: dict) -> str:
    """同步热点股票任务"""
    return execute_dynamic_task({
        'script_path': 'curs/collection/hot_stocks.py',
        'function_name': 'sync_hot_stocks_to_db'
    })


def task_collect_hot_stocks(config: dict) -> str:
    """东方财富热点股票采集任务"""
    return execute_dynamic_task({
        'script_path': 'data_collection/eastmoney_hot_stocks.py',
        'function_name': 'main'
    })


def task_sync_stock_info(config: dict) -> str:
    """同步股票信息任务"""
    try:
        from curs.database import get_db_manager
        
        db = get_db_manager()
        result = db.sync_stock_info_from_qmt()
        
        return f"同步完成: 成功 {result.get('success_count', 0)}, 失败 {result.get('failed_count', 0)}"
    except Exception as e:
        logger.exception("同步股票信息任务失败")
        return f"执行失败: {e}"


def task_profit_analysis(config: dict) -> str:
    """盈利分析任务"""
    return "盈利分析任务执行完成"


def task_clear_hot_stocks(config: dict) -> str:
    """清除热点股票任务"""
    try:
        from curs.database import get_db_manager
        
        db = get_db_manager()
        
        stocks = db.get_stock_pool(category='hot', active_only=False)
        cleared = 0
        for stock in stocks:
            if db.remove_stock_from_pool(stock['stock_code']):
                cleared += 1
        
        return f"已清除 {cleared} 只热点股票"
    except Exception as e:
        logger.exception("清除热点股票任务失败")
        return f"执行失败: {e}"


def register_all_tasks(scheduler):
    """注册所有任务回调"""
    # 注册内置任务
    scheduler.register_callback('sync_hot_stocks', task_sync_hot_stocks)
    scheduler.register_callback('collect_hot_stocks', task_collect_hot_stocks)
    scheduler.register_callback('sync_stock_info', task_sync_stock_info)
    scheduler.register_callback('profit_analysis', task_profit_analysis)
    scheduler.register_callback('clear_hot_stocks', task_clear_hot_stocks)
    
    # 注册动态任务执行器（用于自定义脚本任务）
    scheduler.register_callback('custom_script', execute_dynamic_task)
    scheduler.register_callback('custom', execute_dynamic_task)
    
    logger.info("所有任务回调已注册")