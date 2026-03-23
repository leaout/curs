# coding: utf-8
"""
东方财富热点股票获取模块
支持代理：设置环境变量 HTTP_PROXY 或 HTTPS_PROXY
"""
import akshare as ak
import time
import random
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


def get_hot_stocks(delay: float = 10.0) -> Optional[List[Dict]]:
    """获取东方财富热点股票"""
    # 添加随机延迟避免被封
    actual_delay = delay + random.uniform(2, 5)
    stocks = get_hot_stocks_eastmoney(delay=actual_delay)
    
    if stocks:
        save_cache(stocks)
        return stocks
    
    # 失败则使用缓存
    logger.warning("获取失败，尝试使用缓存")
    cached = load_cache()
    if cached:
        logger.info(f"使用缓存数据: {len(cached)} 只股票")
        return cached
    
    return None


def sync_hot_stocks_to_db(db_manager, category: str = 'hot') -> Dict:
    """同步热点股票到数据库"""
    stocks = get_hot_stocks()
    
    if not stocks:
        return {'success': False, 'message': '获取热点股票失败'}
    
    success_count = 0
    failed_count = 0
    
    for stock in stocks:
        try:
            db_manager.remove_stock_from_pool(stock['code'])
            
            result = db_manager.add_stock_to_pool(
                stock_code=stock['code'],
                stock_name=stock.get('name', ''),
                category=category,
                added_by='auto_sync',
                notes=f"排名:{stock.get('rank', 0)},价格:{stock.get('price', 0)},涨跌:{stock.get('change_pct', 0)}%"
            )
            
            if result:
                success_count += 1
            else:
                failed_count += 1
                
        except Exception as e:
            logger.error(f"同步股票失败: {stock.get('code')}, {e}")
            failed_count += 1
    
    return {
        'success': True,
        'total': len(stocks),
        'success_count': success_count,
        'failed_count': failed_count
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # 检查代理
    proxy = os.environ.get('HTTP_PROXY') or os.environ.get('HTTPS_PROXY')
    if proxy:
        print(f"代理已设置: {proxy}")
    else:
        print("未设置代理（设置环境变量 HTTP_PROXY 或 HTTPS_PROXY 可使用代理）")
    
    stocks = get_hot_stocks(delay=3.0)
    
    if stocks:
        print(f"获取到 {len(stocks)} 只热点股票:")
        for s in stocks[:10]:
            print(f"  {s['rank']}. {s['code']} {s['name']} 涨跌:{s.get('change_pct', 0)}%")
    else:
        print("获取失败")
