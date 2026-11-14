# coding: utf-8
"""同花顺热门股票采集器，抓取 WhatsHot 公开网页榜单。"""
import os
import sys
import logging
from datetime import datetime
from typing import List, Dict

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


def get_ths_hot_stocks() -> List[Dict]:
    """获取 whatshot.top 公开页面上的同花顺热股榜。"""
    from curs.collection.whatshot_hot_stocks import get_whatshot_hot_stocks

    stocks = get_whatshot_hot_stocks()
    if not stocks:
        logger.warning("WhatsHot 同花顺热股榜没有返回数据")
        return []
    return stocks


def save_to_database(stocks: List[Dict]) -> Dict:
    """保存股票到数据库（hot_stock_daily 表）"""
    try:
        from curs.database import get_db_manager

        db = get_db_manager()
        today = datetime.now().strftime('%Y-%m-%d')

        result = db.save_hot_stock_daily(today, stocks)
        logger.info(f"同花顺热点日记录保存: {result}")
        return result

    except Exception as e:
        logger.error(f"数据库操作出错: {e}")
        return {'success': False, 'message': str(e)}


def main(config: dict = None) -> Dict:
    """主函数：获取同花顺热点股票并保存到数据库"""
    print(f"开始获取同花顺热点股票... {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    stocks = get_ths_hot_stocks()

    if not stocks:
        print("获取失败，未获取到任何股票")
        return {'success': False, 'message': '未获取到任何股票'}

    result = save_to_database(stocks)

    print(f"\n执行完成:")
    print(f"  获取股票: {len(stocks)} 只")
    print(f"  保存成功: {result.get('success_count', 0)} 只")

    return {
        'success': True,
        'total': len(stocks),
        'success_count': result.get('success_count', 0),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s - %(message)s')
    print(main())
