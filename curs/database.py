# coding: utf-8
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class DatabaseManager:
    """数据库管理器"""

    def __init__(self, host="192.168.68.150", port="6432", database="postgres",
                 user="postgres", password="chenly.1"):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.connection = None

    def connect(self):
        """连接数据库"""
        try:
            self.connection = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )
            logger.info("数据库连接成功")
            return True
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            return False

    def disconnect(self):
        """断开数据库连接"""
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.info("数据库连接已断开")

    def execute_query(self, query: str, params: tuple = None) -> List[Dict]:
        """执行查询并返回结果"""
        if not self.connection:
            if not self.connect():
                return []

        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                if cursor.description:  # 如果是SELECT查询
                    results = cursor.fetchall()
                    return [dict(row) for row in results]
                else:  # 如果是INSERT/UPDATE/DELETE查询
                    self.connection.commit()
                    return []
        except Exception as e:
            logger.error(f"执行查询失败: {e}")
            self.connection.rollback()
            return []

    def save_strategy_signal(self, strategy_name: str, stock_code: str, signal_type: str,
                           price: float = None, volume: int = None, order_id: str = None,
                           status: str = 'PENDING') -> bool:
        """保存策略信号到数据库"""
        query = """
            INSERT INTO strategy_signals
            (strategy_name, stock_code, signal_type, price, volume, order_id, status, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """

        timestamp = datetime.now()
        params = (strategy_name, stock_code, signal_type, price, volume, order_id, status, timestamp)

        result = self.execute_query(query, params)
        if result is not None:  # execute_query在非SELECT时返回[]
            logger.info(f"策略信号已保存: {strategy_name} - {signal_type} - {stock_code}")
            return True
        else:
            logger.error(f"保存策略信号失败: {strategy_name} - {signal_type} - {stock_code}")
            return False

    def get_strategy_signals(self, strategy_name: str = None, stock_code: str = None,
                           signal_type: str = None, status: str = None,
                           limit: int = 100) -> List[Dict]:
        """获取策略信号"""
        conditions = []
        params = []

        if strategy_name:
            conditions.append("strategy_name = %s")
            params.append(strategy_name)

        if stock_code:
            conditions.append("stock_code = %s")
            params.append(stock_code)

        if signal_type:
            conditions.append("signal_type = %s")
            params.append(signal_type)

        if status:
            conditions.append("status = %s")
            params.append(status)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = f"""
            SELECT * FROM strategy_signals
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT %s
        """
        params.append(limit)

        return self.execute_query(query, tuple(params))

    def update_signal_status(self, signal_id: int, status: str, order_id: str = None) -> bool:
        """更新信号状态"""
        if order_id:
            query = "UPDATE strategy_signals SET status = %s, order_id = %s WHERE id = %s"
            params = (status, order_id, signal_id)
        else:
            query = "UPDATE strategy_signals SET status = %s WHERE id = %s"
            params = (status, signal_id)

        result = self.execute_query(query, params)
        if result is not None:
            logger.info(f"信号状态已更新: ID={signal_id}, 状态={status}")
            return True
        else:
            logger.error(f"更新信号状态失败: ID={signal_id}")
            return False

    def update_signal_status_by_order_id(self, order_id: str, status: str) -> bool:
        """根据订单ID更新信号状态"""
        query = "UPDATE strategy_signals SET status = %s WHERE order_id = %s"
        params = (status, order_id)

        result = self.execute_query(query, params)
        if result is not None:
            logger.info(f"信号状态已更新: 订单ID={order_id}, 状态={status}")
            return True
        else:
            logger.error(f"更新信号状态失败: 订单ID={order_id}")
            return False

    def create_tables(self):
        """创建数据库表"""
        try:
            with open('data/create_trading_tables.sql', 'r', encoding='utf-8') as f:
                sql_script = f.read()

            # 分割SQL语句并执行
            statements = sql_script.split(';')
            for statement in statements:
                statement = statement.strip()
                if statement:
                    self.execute_query(statement)

            logger.info("数据库表创建成功")
            return True
        except Exception as e:
            logger.error(f"创建数据库表失败: {e}")
            return False

# 全局数据库管理器实例
_db_manager = None

def get_db_manager() -> DatabaseManager:
    """获取数据库管理器实例"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager
