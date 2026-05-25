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

COLLECTED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'collected')


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
    """导入股票数据到 stock_pool 表"""
    if db_manager is None:
        from curs.database import get_db_manager
        db_manager = get_db_manager()

    success_count = 0
    failed_count = 0
    failed_stocks = []

    for stock in stocks:
        try:
            # 先删除旧记录再插入（upsert）
            db_manager.remove_stock_from_pool(stock['code'])
            ok = db_manager.add_stock_to_pool(
                stock_code=stock['code'],
                stock_name=stock.get('name', ''),
                category='hot',
                added_by='github_actions',
                notes=f"排名:{stock.get('rank', 0)},价格:{stock.get('price', 0)},涨跌:{stock.get('change_pct', 0)}%,采集时间:{stock.get('collect_time', '')}"
            )
            if ok:
                success_count += 1
            else:
                failed_count += 1
                failed_stocks.append(stock['code'])
        except Exception as e:
            logger.error(f"导入失败 {stock.get('code')}: {e}")
            failed_count += 1
            failed_stocks.append(stock['code'])

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
