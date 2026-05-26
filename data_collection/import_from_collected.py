# coding: utf-8
"""
将 GitHub Actions 采集的 JSON 数据导入本地 PostgreSQL 数据库（stock_pool 表）
"""
import os
import sys
import json
import glob
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logger = logging.getLogger(__name__)

DB_CONFIG = None
COLLECTED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'collected')


def _get_db_config():
    global DB_CONFIG
    if DB_CONFIG is None:
        from curs.utils.config import load_yaml
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.yml')
        config = load_yaml(config_path) or {}
        db = config.get('database', {})
        DB_CONFIG = {
            'host': db.get('host', '192.168.2.12'),
            'port': db.get('port', 6432),
            'database': db.get('database', 'postgres'),
            'user': db.get('user', 'postgres'),
            'password': db.get('password', 'chenly.1'),
        }
    return DB_CONFIG


def _get_connection():
    import psycopg2
    cfg = _get_db_config()
    conn = psycopg2.connect(**cfg)
    conn.autocommit = True
    return conn


def find_latest_json() -> str:
    """找到最新的 hot_stocks_YYYYMMDD.json 文件"""
    pattern = os.path.join(COLLECTED_DIR, 'hot_stocks_[0-9]*.json')
    files = glob.glob(pattern)
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def load_stocks_from_file(filepath: str) -> list:
    """从 JSON 文件加载股票数据"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        stocks = data.get('stocks', [])
        logger.info(f"从 {os.path.basename(filepath)} 加载 {len(stocks)} 只股票")
        return stocks
    except Exception as e:
        logger.error(f"加载文件失败 {filepath}: {e}")
        return []


def import_to_database(stocks: list, db_manager=None) -> dict:
    """导入股票数据到 stock_pool 表（使用独立连接，避免锁冲突）"""
    conn = _get_connection()
    cur = conn.cursor()

    # 先清空旧 hot 数据
    cur.execute("DELETE FROM stock_pool WHERE category = 'hot'")

    success_count = 0
    failed_count = 0
    failed_stocks = []

    for stock in stocks:
        try:
            cur.execute("""
                INSERT INTO stock_pool
                    (stock_code, stock_name, category, added_by, notes)
                VALUES (%s, %s, 'hot', 'github_actions', %s)
                ON CONFLICT (stock_code) DO UPDATE SET
                    stock_name = EXCLUDED.stock_name,
                    notes = EXCLUDED.notes,
                    updated_at = CURRENT_TIMESTAMP,
                    is_active = TRUE
            """, (
                stock['code'],
                stock.get('name', ''),
                f"排名:{stock.get('rank', 0)},价格:{stock.get('price', 0)},涨跌:{stock.get('change_pct', 0)}%,采集时间:{stock.get('collect_time', '')}"
            ))
            success_count += 1
        except Exception as e:
            logger.error(f"导入失败 {stock.get('code')}: {e}")
            failed_count += 1
            failed_stocks.append(stock['code'])

    cur.close()
    conn.close()

    return {
        'success': True,
        'total': len(stocks),
        'success_count': success_count,
        'failed_count': failed_count,
        'failed_stocks': failed_stocks
    }


def main(config: dict = None) -> str:
    logger.info("=" * 50)
    logger.info("开始导入 GitHub Actions 采集数据")

    # 从 config 中获取是否先拉取代码
    if config and config.get('git_pull'):
        try:
            logger.info("正在拉取远程采集数据...")
            result = os.system('git pull origin master --ff-only')
            if result == 0:
                logger.info("git pull 成功")
            else:
                logger.warning("git pull 可能失败，继续使用本地数据")
        except Exception as e:
            logger.warning(f"git pull 异常: {e}")

    filepath = find_latest_json()
    if not filepath:
        msg = "未找到采集数据文件 (data/collected/hot_stocks_*.json)"
        logger.warning(msg)
        return msg

    stocks = load_stocks_from_file(filepath)
    if not stocks:
        msg = "加载股票数据为空"
        logger.warning(msg)
        return msg

    result = import_to_database(stocks)
    msg = (f"导入完成: 共 {result['total']} 只, "
           f"成功 {result['success_count']}, "
           f"失败 {result['failed_count']}")
    logger.info(msg)
    if result['failed_stocks']:
        logger.warning(f"失败股票: {result['failed_stocks']}")
    logger.info("=" * 50)
    return msg


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s - %(message)s')
    print(main())
