# coding: utf-8
"""
将 GitHub Actions 采集的 JSON 数据导入本地 PostgreSQL 数据库（stock_pool 表）
"""
import os
import sys
import json
import glob
import logging
import re
from datetime import datetime
from zoneinfo import ZoneInfo

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
            'host': db.get('host', '192.168.2.238'),
            'port': db.get('port', 6432),
            'database': db.get('database', 'postgres'),
            'user': db.get('user', 'postgres'),
            'password': db.get('password', 'chenly.1'),
        }
    return DB_CONFIG


def _get_connection():
    import psycopg2
    cfg = _get_db_config()
    conn = psycopg2.connect(**cfg, connect_timeout=10)
    conn.autocommit = False
    return conn


def find_latest_json() -> str:
    """找到最新的 hot_stocks_YYYYMMDD.json 文件"""
    pattern = os.path.join(COLLECTED_DIR, 'hot_stocks_[0-9]*.json')
    files = glob.glob(pattern)
    if not files:
        return None
    dated = []
    for path in files:
        match = re.fullmatch(r'hot_stocks_(\d{8})\.json', os.path.basename(path))
        if match:
            try:
                date = datetime.strptime(match[1], '%Y%m%d').date()
                if date <= datetime.now(ZoneInfo('Asia/Shanghai')).date():
                    dated.append((date, path))
            except ValueError:
                continue
    return max(dated)[1] if dated else None


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
    """导入股票数据到 hot_stock_daily + stock_pool 表"""
    logger.info(f"开始导入 {len(stocks)} 只股票数据")
    if not stocks or any(not stock.get('code') for stock in stocks):
        raise ValueError('Empty or invalid stock pool cannot replace existing data')

    # 提取采集日期
    today = datetime.now().strftime('%Y-%m-%d')
    if stocks and stocks[0].get('collect_time'):
        try:
            dt = datetime.fromisoformat(stocks[0]['collect_time'])
            today = dt.strftime('%Y-%m-%d')
        except:
            pass

    # 保存到 hot_stock_daily 日记录表
    if db_manager:
        db_manager.save_hot_stock_daily(today, stocks)

    # 写入 stock_pool（连续上榜过滤由策略启动时自行判断）
    conn = _get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM stock_pool WHERE category = 'hot'")

    success_count = 0
    for stock in stocks:
        try:
            cur.execute("""
                INSERT INTO stock_pool
                    (stock_code, stock_name, category, added_by, notes)
                VALUES (%s, %s, 'hot', 'github_actions', %s)
                ON CONFLICT (stock_code) DO UPDATE SET
                    stock_name = EXCLUDED.stock_name,
                    notes = EXCLUDED.notes,
                    category = 'hot',
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
            conn.rollback()
            cur.close()
            conn.close()
            return {'success': False, 'total': len(stocks), 'success_count': 0,
                    'failed_count': len(stocks), 'failed_stocks': [stock.get('code') for stock in stocks]}

    conn.commit()
    cur.close()
    conn.close()

    return {
        'success': True,
        'total': len(stocks),
        'success_count': success_count,
        'failed_count': 0,
        'failed_stocks': [],
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

    file_date = datetime.strptime(os.path.basename(filepath)[11:19], '%Y%m%d').date()
    max_age = int((config or {}).get('max_age_days', 14))
    if (datetime.now(ZoneInfo('Asia/Shanghai')).date() - file_date).days > max_age:
        msg = f'采集文件过期 ({file_date})，保留现有股票池，不重新导入'
        logger.warning(msg)
        return msg

    stocks = load_stocks_from_file(filepath)
    if not stocks:
        msg = "加载股票数据为空"
        logger.warning(msg)
        return msg

    for stock in stocks:
        if stock.get('collect_time'):
            collected = datetime.fromisoformat(stock['collect_time'].replace('Z', '+00:00'))
            if collected.tzinfo is not None:
                collected = collected.astimezone(ZoneInfo('Asia/Shanghai'))
            age = (datetime.now(ZoneInfo('Asia/Shanghai')).date() - collected.date()).days
            if not 0 <= age <= max_age:
                msg = f'记录原始采集时间过期或在未来 ({stock["collect_time"]})，保留现有股票池'
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
