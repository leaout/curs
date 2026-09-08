# coding: utf-8
"""
Broker 工厂模块
根据配置创建 QMT 或东方财富账户
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
        QmtStockAccount 或 EastMoneyAccount 实例
    """
    broker_type = config.get('broker', 'qmt')

    if broker_type == 'eastmoney':
        return _create_eastmoney_account(config, total_cash)
    else:
        return _create_qmt_account(config, total_cash)


def _create_qmt_account(config: dict, total_cash: float):
    from curs.broker.qmt_account import QmtStockAccount

    qmt_config = config.get("qmt", {})
    qmt_path = qmt_config.get("path", "")
    account_id = qmt_config.get("account_id", "")
    trader_name = qmt_config.get("trader_name", "")

    if not qmt_path or not account_id:
        raise ValueError("QMT 配置不完整：path 或 account_id 缺失")

    return QmtStockAccount(
        path=qmt_path,
        account_id=account_id,
        trader_name=trader_name,
        total_cash=total_cash,
    )


def _create_eastmoney_account(config: dict, total_cash: float):
    from curs.broker.eastmoney_account import EastMoneyAccount

    em_config = config.get("eastmoney", {})
    account_no = em_config.get("account_no", "")
    password = em_config.get("password", "")
    session_file = em_config.get("session_file", "eastmoney_trader.session")

    if not account_no or not password:
        raise ValueError("东方财富配置不完整：account_no 或 password 缺失")

    return EastMoneyAccount(
        account_no=account_no,
        password=password,
        session_file=session_file,
        total_cash=total_cash,
    )
