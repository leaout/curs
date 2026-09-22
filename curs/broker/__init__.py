# coding: utf-8
"""
Broker 工厂模块
根据配置创建东方财富账户
"""

import logging

logger = logging.getLogger(__name__)


def create_account(config: dict, total_cash: float = 100000):
    """
    根据 config 中 broker 字段创建对应的交易账户

    Args:
        config: 应用配置字典
        total_cash: 初始可用资金

    Returns:
        EastMoneyAccount 实例
    """
    broker_type = str(config.get('broker', 'eastmoney')).strip().lower()

    if broker_type == 'eastmoney':
        return _create_eastmoney_account(config, total_cash)
    raise ValueError(f"不支持的交易商: {broker_type}（当前支持: eastmoney）")


def _create_eastmoney_account(config: dict, total_cash: float):
    from curs.broker.eastmoney_account import EastMoneyAccount

    em_config = config.get("eastmoney", {})
    account_no = em_config.get("account_no", "")
    password = em_config.get("password", "")
    session_file = em_config.get("session_file", "data/eastmoney_trader.session")

    if not account_no or not password:
        raise ValueError("东方财富配置不完整：account_no 或 password 缺失")

    return EastMoneyAccount(
        account_no=account_no,
        password=password,
        session_file=session_file,
        total_cash=total_cash,
    )
