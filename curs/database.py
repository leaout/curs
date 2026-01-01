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

    def execute_query(self, query: str, params: tuple = None):
        """执行查询并返回结果"""
        # 检查连接是否存在或已关闭
        if not self.connection or self.connection.closed:
            if not self.connect():
                return None

        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                if cursor.description:  # 如果是SELECT查询
                    results = cursor.fetchall()
                    return [dict(row) for row in results]
                else:  # 如果是INSERT/UPDATE/DELETE查询
                    self.connection.commit()
                    return cursor.rowcount
        except Exception as e:
            logger.error(f"执行查询失败: {e}")
            # 如果查询失败，标记连接为无效，下次会自动重连
            if self.connection:
                try:
                    self.connection.close()
                except:
                    pass
                self.connection = None
            return None

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

    # ===== 股票池管理方法 =====

    def add_stock_to_pool(self, stock_code: str, stock_name: str = None,
                         category: str = 'default', added_by: str = 'web',
                         notes: str = None) -> bool:
        """添加股票到股票池"""
        query = """
            INSERT INTO stock_pool
            (stock_code, stock_name, category, added_by, notes)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (stock_code) DO UPDATE SET
                stock_name = EXCLUDED.stock_name,
                category = EXCLUDED.category,
                notes = EXCLUDED.notes,
                updated_at = CURRENT_TIMESTAMP,
                is_active = TRUE
        """

        params = (stock_code, stock_name, category, added_by, notes)

        result = self.execute_query(query, params)
        if result is not None:
            logger.info(f"股票已添加到股票池: {stock_code}")
            return True
        else:
            logger.error(f"添加股票到股票池失败: {stock_code}")
            return False

    def remove_stock_from_pool(self, stock_code: str) -> bool:
        """从股票池中移除股票"""
        query = "DELETE FROM stock_pool WHERE stock_code = %s"
        params = (stock_code,)

        result = self.execute_query(query, params)
        if result is not None and result > 0:
            logger.info(f"股票已从股票池中移除: {stock_code} ({result} 条记录)")
            return True
        else:
            logger.error(f"从股票池中移除股票失败: {stock_code} (受影响行数: {result})")
            return False

    def batch_add_stocks_to_pool(self, stocks: list, category: str = 'default',
                               added_by: str = 'web') -> dict:
        """批量添加股票到股票池"""
        success_count = 0
        failed_stocks = []

        for stock in stocks:
            if isinstance(stock, dict):
                stock_code = stock.get('code', '')
                stock_name = stock.get('name', '')
                notes = stock.get('notes', '')
            else:
                stock_code = str(stock).strip()
                stock_name = None
                notes = None

            if stock_code:
                if self.add_stock_to_pool(stock_code, stock_name, category, added_by, notes):
                    success_count += 1
                else:
                    failed_stocks.append(stock_code)

        return {
            'success_count': success_count,
            'failed_count': len(failed_stocks),
            'failed_stocks': failed_stocks
        }

    def batch_remove_stocks_from_pool(self, stock_codes: list) -> dict:
        """批量从股票池中移除股票"""
        success_count = 0
        failed_stocks = []

        for stock_code in stock_codes:
            if self.remove_stock_from_pool(stock_code.strip()):
                success_count += 1
            else:
                failed_stocks.append(stock_code)

        return {
            'success_count': success_count,
            'failed_count': len(failed_stocks),
            'failed_stocks': failed_stocks
        }

    def get_stock_pool(self, category: str = None, active_only: bool = True,
                      limit: int = 1000, offset: int = 0) -> List[Dict]:
        """获取股票池"""
        conditions = []
        params = []

        if category:
            conditions.append("category = %s")
            params.append(category)

        if active_only:
            conditions.append("is_active = TRUE")

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = f"""
            SELECT * FROM stock_pool
            WHERE {where_clause}
            ORDER BY added_at DESC
            LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])

        return self.execute_query(query, tuple(params))

    def update_stock_pool_category(self, stock_code: str, category: str) -> bool:
        """更新股票池中股票的分类"""
        query = "UPDATE stock_pool SET category = %s, updated_at = CURRENT_TIMESTAMP WHERE stock_code = %s"
        params = (category, stock_code)

        result = self.execute_query(query, params)
        if result is not None and result > 0:
            logger.info(f"股票分类已更新: {stock_code} -> {category} ({result} 条记录)")
            return True
        else:
            logger.error(f"更新股票分类失败: {stock_code} (受影响行数: {result})")
            return False

    def get_stock_pool_stats(self) -> Dict:
        """获取股票池统计信息"""
        # 总股票数
        total_query = "SELECT COUNT(*) as total FROM stock_pool WHERE is_active = TRUE"
        total_result = self.execute_query(total_query)
        total_stocks = total_result[0]['total'] if total_result else 0

        # 按分类统计
        category_query = """
            SELECT category, COUNT(*) as count
            FROM stock_pool
            WHERE is_active = TRUE
            GROUP BY category
            ORDER BY count DESC
        """
        category_stats = self.execute_query(category_query)

        return {
            'total_stocks': total_stocks,
            'category_stats': category_stats or []
        }

    # ===== 涨停股票管理方法 =====

    def add_zt_stock(self, trade_date: str, stock_code: str) -> bool:
        """添加涨停股票记录"""
        query = """
            INSERT INTO zt_stocks (trade_date, stock_code)
            VALUES (%s, %s)
            ON CONFLICT (trade_date, stock_code) DO NOTHING
        """

        params = (trade_date, stock_code)

        result = self.execute_query(query, params)
        if result is not None:
            logger.info(f"涨停股票记录已添加: {trade_date} - {stock_code}")
            return True
        else:
            logger.error(f"添加涨停股票记录失败: {trade_date} - {stock_code}")
            return False

    def get_zt_stocks_by_date(self, trade_date: str) -> List[str]:
        """根据日期获取涨停股票列表"""
        query = "SELECT stock_code FROM zt_stocks WHERE trade_date = %s ORDER BY stock_code"
        params = (trade_date,)

        results = self.execute_query(query, params)
        return [row['stock_code'] for row in results]

    def get_zt_stocks_by_date_range(self, start_date: str, end_date: str) -> List[Dict]:
        """获取日期范围内的涨停股票"""
        query = """
            SELECT trade_date, stock_code
            FROM zt_stocks
            WHERE trade_date BETWEEN %s AND %s
            ORDER BY trade_date DESC, stock_code
        """
        params = (start_date, end_date)

        return self.execute_query(query, params)

    def get_latest_zt_stocks(self, days: int = 1) -> List[str]:
        """获取最近N天的涨停股票"""
        query = """
            SELECT DISTINCT stock_code
            FROM zt_stocks
            WHERE trade_date >= CURRENT_DATE - INTERVAL '%s days'
            ORDER BY stock_code
        """
        params = (days,)

        results = self.execute_query(query, params)
        return [row['stock_code'] for row in results]

    def batch_add_zt_stocks(self, zt_data: List[Dict]) -> dict:
        """批量添加涨停股票记录"""
        success_count = 0
        failed_count = 0

        for item in zt_data:
            trade_date = item.get('trade_date')
            stock_code = item.get('stock_code')

            if trade_date and stock_code:
                if self.add_zt_stock(trade_date, stock_code):
                    success_count += 1
                else:
                    failed_count += 1

        return {
            'success_count': success_count,
            'failed_count': failed_count,
            'total_count': len(zt_data)
        }

    def get_hot_stocks_from_pool(self, category: str = 'hot') -> List[str]:
        """从股票池中获取指定分类的股票代码"""
        query = "SELECT stock_code FROM stock_pool WHERE category = %s AND is_active = TRUE ORDER BY updated_at desc limit 100"
        params = (category,)

        results = self.execute_query(query, params)
        return [row['stock_code'] for row in results]

    def get_all_active_stocks_from_pool(self) -> List[str]:
        """获取股票池中所有激活的股票代码"""
        # query = "SELECT stock_code FROM stock_pool WHERE is_active = TRUE ORDER BY stock_code"
        query = "SELECT stock_code FROM stock_pool WHERE is_active = TRUE ORDER BY updated_at desc limit 100"

        results = self.execute_query(query)
        return [row['stock_code'] for row in results]

# 全局数据库管理器实例
_db_manager = None

def get_db_manager() -> DatabaseManager:
    """获取数据库管理器实例"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager
