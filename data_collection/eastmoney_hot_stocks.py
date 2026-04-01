# coding: utf-8
"""
东方财富热点股票采集器
支持代理：设置环境变量 HTTP_PROXY 或 HTTPS_PROXY
"""
import os
import sys
import random

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import akshare as ak
import pandas as pd
from datetime import datetime
from typing import List, Dict

# ==================== 代理配置 ====================
PROXY_CONFIG = {
    'enabled': True,
    'proxy_type': 'http',
    'proxy_host': '192.168.100.1',
    'proxy_port': '7890',
    'timeout': 10,
    'retry_times': 3,
    'use_random_user_agent': True
}

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]


def get_proxy_config():
    """获取代理配置"""
    if not PROXY_CONFIG['enabled']:
        return None
    
    proxy_url = f"{PROXY_CONFIG['proxy_type']}://{PROXY_CONFIG['proxy_host']}:{PROXY_CONFIG['proxy_port']}"
    return {'http': proxy_url, 'https': proxy_url}


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
    
    if original_code.startswith(('SH', 'SZ')):
        market = original_code[:2]
        code_num = original_code[2:]
        return f"{code_num}.{market}"
    
    return original_code


def get_eastmoney_hot_stocks(delay: float = 3.0) -> List[Dict]:
    """
    获取东方财富热点股票排名数据
    """
    import time
    time.sleep(delay + random.uniform(1, 3))
    
    # 设置代理
    if PROXY_CONFIG['enabled']:
        proxy_url = f"{PROXY_CONFIG['proxy_type']}://{PROXY_CONFIG['proxy_host']}:{PROXY_CONFIG['proxy_port']}"
        os.environ['HTTP_PROXY'] = proxy_url
        os.environ['HTTPS_PROXY'] = proxy_url
    
    try:
        df = ak.stock_hot_rank_em()
        
        stocks = []
        for idx, row in df.head(100).iterrows():
            code = str(row.get("代码", "")).strip()
            if not code:
                continue
            
            formatted_code = format_stock_code(code)
            
            # 过滤 ST、*ST、688、300、北交所
            if formatted_code.startswith(('688', '30')) or formatted_code.endswith('.BJ'):
                continue
            
            # 股票名称包含 ST
            name = str(row.get("股票名称", ""))
            if name.startswith('ST') or name.startswith('*ST'):
                continue
            
            stocks.append({
                'code': formatted_code,
                'name': name,
                'price': row.get("最新价", 0) or 0,
                'change_pct': float(row.get("涨跌幅", 0) or 0),
                'rank': int(row.get("当前排名", idx + 1) or idx + 1),
                'source': '东方财富'
            })
        
        print(f"成功获取 {len(stocks)} 只东方财富热点股票")
        return stocks
        
    except Exception as e:
        print(f"获取东方财富数据失败: {e}")
        return []


def save_to_database(stocks: List[Dict]) -> Dict:
    """保存股票到数据库"""
    from curs.database import get_db_manager
    
    try:
        db = get_db_manager()
        
        success_count = 0
        failed_count = 0
        
        for stock in stocks:
            try:
                # 先删除旧记录
                db.remove_stock_from_pool(stock['code'])
                
                # 添加新记录
                result = db.add_stock_to_pool(
                    stock_code=stock['code'],
                    stock_name=stock.get('name', ''),
                    category='hot',
                    added_by='eastmoney_collector',
                    notes=f"排名:{stock['rank']}, 价格:{stock['price']}, 涨跌:{stock['change_pct']}%"
                )
                
                if result:
                    success_count += 1
                else:
                    failed_count += 1
                    
            except Exception as e:
                print(f"保存股票失败 {stock.get('code')}: {e}")
                failed_count += 1
        
        return {
            'success': True,
            'total': len(stocks),
            'success_count': success_count,
            'failed_count': failed_count
        }
        
    except Exception as e:
        print(f"数据库操作出错: {e}")
        return {'success': False, 'message': str(e)}


def main():
    """主函数"""
    print(f"开始获取东方财富热点股票... {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"代理状态: {'启用' if PROXY_CONFIG['enabled'] else '禁用'}")
    
    stocks = get_eastmoney_hot_stocks()
    
    if not stocks:
        print("获取失败，未获取到任何股票")
        return
    
    result = save_to_database(stocks)
    
    print(f"\n执行完成:")
    print(f"  获取股票: {result.get('total', 0)} 只")
    print(f"  成功保存: {result.get('success_count', 0)} 只")
    print(f"  保存失败: {result.get('failed_count', 0)} 只")


if __name__ == "__main__":
    main()