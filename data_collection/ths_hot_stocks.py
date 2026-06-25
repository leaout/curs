# coding: utf-8
"""
同花顺热门股票采集器
使用 pywencai 获取同花顺问财热门个股排名数据
"""
import os
import sys
import logging
from datetime import datetime
from typing import List, Dict

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


def get_ths_hot_stocks() -> List[Dict]:
    """获取同花顺热门个股排名（前100只）"""
    try:
        import pywencai
    except ImportError:
        logger.error("缺少 pywencai 依赖，请安装: pip install pywencai")
        return []

    try:
        df = pywencai.get(query='热门个股排名前100', loop=True)
        if df is None or len(df) == 0:
            logger.warning("同花顺热点股票数据为空")
            return []

        stocks = []
        for _, row in df.iterrows():
            code = str(row.get('股票代码', '')).strip()
            name = str(row.get('股票简称', '')).strip()
            price = float(row.get('最新价', 0) or 0)
            change_pct = float(row.get('最新涨跌幅', 0) or 0)
            rank_col = [c for c in df.columns if '排名' in c]
            rank = int(float(row.get(rank_col[0], 0)) or 0) if rank_col else 0

            if not code:
                continue

            # 过滤 ST、*ST
            if name.startswith('ST') or name.startswith('*ST'):
                continue

            stocks.append({
                'code': code,       # 已含后缀，如 000725.SZ
                'name': name,
                'price': price,
                'change_pct': change_pct,
                'rank': rank,
                'source': '同花顺'
            })

        logger.info(f"成功获取 {len(stocks)} 只同花顺热点股票")
        return stocks

    except Exception as e:
        logger.error(f"获取同花顺数据失败: {e}", exc_info=True)
        return []


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
