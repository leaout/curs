# coding: utf-8
"""WhatsHot 同花顺热股榜采集与股票池同步。"""
import time
import logging
import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

CACHE_FILE = 'data/hotstocks_cache.json'
CACHE_EXPIRE_HOURS = 24


def format_stock_code(original_code: str) -> str:
    """将原始代码转换为标准格式"""
    if not original_code:
        return ""
    original_code = str(original_code).strip()
    
    if '.' in original_code:
        return original_code
    
    if len(original_code) == 6:
        if original_code.startswith('6'):
            return f"{original_code}.SH"
        else:
            return f"{original_code}.SZ"
    
    market = original_code[:2].upper()
    code_num = original_code[2:]
    
    if market == "SH":
        return f"{code_num}.SH"
    elif market == "SZ":
        return f"{code_num}.SZ"
    return original_code


def load_cache() -> Optional[List[Dict]]:
    """加载缓存数据"""
    if not os.path.exists(CACHE_FILE):
        logger.info("缓存文件不存在")
        return None
    
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        cache_time = datetime.fromisoformat(data.get('update_time', '2000-01-01'))
        if datetime.now() - cache_time > timedelta(hours=CACHE_EXPIRE_HOURS):
            logger.info("缓存已过期")
            return None
        
        return data.get('stocks', [])
    except Exception as e:
        logger.warning(f"加载缓存失败: {e}")
        return None


def save_cache(stocks: List[Dict]):
    """保存缓存"""
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        data = {
            'update_time': datetime.now().isoformat(),
            'stocks': stocks
        }
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"缓存已保存: {len(stocks)} 只股票")
    except Exception as e:
        logger.error(f"保存缓存失败: {e}")


def get_hot_stocks_eastmoney(delay: float = 10.0) -> Optional[List[Dict]]:
    """获取东方财富热点股票"""
    try:
        import akshare as ak

        logger.info(f"正在获取东方财富热点股票（延迟{delay}秒）...")
        time.sleep(delay)
        
        stock_hot_rank_em_df = ak.stock_hot_rank_em()
        
        stocks = []
        for idx, row in stock_hot_rank_em_df.head(100).iterrows():
            code = str(row.get("代码", "")).strip()
            if not code:
                continue
            
            formatted_code = format_stock_code(code)
            stocks.append({
                'code': formatted_code,
                'name': str(row.get("股票名称", "")),
                'price': row.get("最新价", 0) or 0,
                'change_pct': float(row.get("涨跌幅", 0) or 0),
                'rank': int(row.get("当前排名", idx + 1) or idx + 1)
            })
        
        logger.info(f"成功获取东方财富热点股票: {len(stocks)} 只")
        return stocks
        
    except Exception as e:
        logger.error(f"获取东方财富热点股票失败: {e}")
        return None


def get_hot_stocks(delay: float = 10.0, allow_cache: bool = False) -> Optional[List[Dict]]:
    """获取 WhatsHot 同花顺榜单；默认不以旧缓存冒充当天数据。"""
    from curs.collection.whatshot_hot_stocks import get_whatshot_hot_stocks

    stocks = get_whatshot_hot_stocks()
    
    if stocks:
        save_cache(stocks)
        return stocks
    
    if allow_cache:
        logger.warning("WhatsHot 获取失败，尝试使用有效期内缓存（可能不是当天数据）")
        cached = load_cache()
        if cached:
            logger.info(f"使用缓存数据: {len(cached)} 只股票")
            return cached

    # 不直接请求东方财富或同花顺上游，避免绕过用户选择的来源并增加限流风险。
    logger.warning("WhatsHot 获取失败；本次不使用旧缓存")
    
    return None


def sync_hot_stocks_to_db(db_manager, category: str = 'hot', trade_date: str = None) -> Dict:
    """抓取实时榜单并同步到股票池和每日快照；抓取失败时不落旧缓存。"""
    stocks = get_hot_stocks(allow_cache=False)

    if not stocks:
        return {'success': False, 'message': '获取热点股票失败'}

    from zoneinfo import ZoneInfo
    today = trade_date or datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d')
    source = stocks[0].get('source', '未知来源')
    fetched_at = stocks[0].get('source_fetched_at') or ''
    source_update_time = stocks[0].get('source_update_time', '')

    # 先 upsert 当前榜单，再清理不再上榜的热点股；完整成功后才写入日快照。
    success_count = 0
    for stock in stocks:
        try:
            result = db_manager.add_stock_to_pool(
                stock_code=stock['code'],
                stock_name=stock.get('name', ''),
                category=category,
                added_by='auto_sync',
                notes=(
                    f"数据来源:{stock.get('source', source)},采集时间:{stock.get('source_fetched_at', fetched_at)},"
                    f"排名:{stock.get('rank', 0)},价格:{stock.get('price', 0)},"
                    f"涨跌:{stock.get('change_pct', 0)}%,热度:{stock.get('hot', '')},"
                    f"榜单更新时间:{stock.get('source_update_time', source_update_time)}"
                )
            )
            if result:
                success_count += 1
        except Exception as e:
            logger.error(f"同步股票失败: {stock.get('code')}, {e}")

    if success_count != len(stocks):
        return {
            'success': False,
            'message': '股票池写入不完整，日快照未标记为完成',
            'total': len(stocks),
            'success_count': success_count,
            'source': source,
            'fetched_at': fetched_at,
        }

    existing_hot_stocks = db_manager.get_stock_pool(category=category, active_only=False)
    if existing_hot_stocks is None:
        return {
            'success': False,
            'message': '无法读取现有热点股票，日快照未标记为完成',
            'total': len(stocks),
            'success_count': success_count,
            'source': source,
            'fetched_at': fetched_at,
        }
    current_codes = {stock['code'] for stock in stocks}
    for existing in existing_hot_stocks:
        old_code = existing.get('stock_code')
        if old_code and old_code not in current_codes:
            if not db_manager.remove_stock_from_pool(old_code):
                return {
                    'success': False,
                    'message': '清理过期热点股票失败: {}'.format(old_code),
                    'total': len(stocks),
                    'success_count': success_count,
                    'source': source,
                    'fetched_at': fetched_at,
                }

    daily_result = db_manager.save_hot_stock_daily(today, stocks)
    if not daily_result or not daily_result.get('success') or daily_result.get('success_count') != len(stocks):
        return {
            'success': False,
            'message': '保存热点榜日记录失败: {}'.format((daily_result or {}).get('message', '记录数量不完整')),
            'source': source,
            'fetched_at': fetched_at,
        }

    return {
        'success': True,
        'total': len(stocks),
        'success_count': success_count,
        'source': source,
        'fetched_at': fetched_at,
        'source_update_time': source_update_time,
        'daily_saved_count': daily_result.get('success_count', 0),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # 检查代理
    proxy = os.environ.get('HTTP_PROXY') or os.environ.get('HTTPS_PROXY')
    if proxy:
        print(f"代理已设置: {proxy}")
    else:
        print("未设置代理（设置环境变量 HTTP_PROXY 或 HTTPS_PROXY 可使用代理）")
    
    stocks = get_hot_stocks(delay=3.0, allow_cache=False)
    
    if stocks:
        print(f"获取到 {len(stocks)} 只热点股票:")
        for s in stocks[:10]:
            print(f"  {s['rank']}. {s['code']} {s['name']} 涨跌:{s.get('change_pct', 0)}%")
    else:
        print("获取失败")
