# coding: utf-8
"""GitHub Actions 定时采集脚本：渲染 WhatsHot 公开页并输出同花顺热股 JSON/CSV。"""
import os
import sys
import json
import csv
import logging
from datetime import datetime
from typing import List, Dict
from zoneinfo import ZoneInfo

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'collected')
SHANGHAI = ZoneInfo('Asia/Shanghai')


def format_stock_code(original_code: str) -> str:
    if not original_code:
        return ""
    original_code = str(original_code).strip()
    if '.' in original_code:
        return original_code
    if len(original_code) == 6:
        return f"{original_code}.SH" if original_code.startswith('6') else f"{original_code}.SZ"
    market = original_code[:2].upper()
    code_num = original_code[2:]
    if market == "SH":
        return f"{code_num}.SH"
    elif market == "SZ":
        return f"{code_num}.SZ"
    return original_code


def load_cache() -> List[Dict]:
    """从 latest.json 加载上次成功的缓存"""
    path = os.path.join(DATA_DIR, 'hot_stocks_latest.json')
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        stocks = data.get('stocks', [])
        logger.info(f"从缓存加载 {len(stocks)} 只股票")
        return stocks
    except Exception as e:
        logger.warning(f"缓存加载失败: {e}")
        return []


def collect_hot_stocks(max_retries: int = 3) -> List[Dict]:
    """读取 WhatsHot 热股榜；不以旧名单冒充当天数据。"""
    from curs.collection.whatshot_hot_stocks import get_whatshot_hot_stocks

    for attempt in range(1, max(1, max_retries) + 1):
        stocks = get_whatshot_hot_stocks()
        if stocks:
            collected_at = datetime.now(SHANGHAI).strftime('%Y-%m-%d %H:%M:%S')
            for stock in stocks:
                stock['collect_time'] = collected_at
            logger.info('成功获取 %s 只 WhatsHot 同花顺热股', len(stocks))
            return stocks
        if attempt < max_retries:
            logger.warning('WhatsHot 热股榜采集失败，将重试 %s/%s', attempt, max_retries)
            import time
            time.sleep(min(5 * attempt, 15))

    logger.error('WhatsHot 热股榜采集失败；未生成新名单')
    return []


def save_to_json(stocks: List[Dict], label: str = 'hot_stocks'):
    """保存为 JSON 文件"""
    os.makedirs(DATA_DIR, exist_ok=True)
    today = datetime.now(SHANGHAI).strftime('%Y%m%d')
    filepath = os.path.join(DATA_DIR, f'{label}_{today}.json')

    data = {
        'update_time': datetime.now(SHANGHAI).isoformat(),
        'date': today,
        'total': len(stocks),
        'stocks': stocks
    }
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 同时更新 latest.json
    latest_path = os.path.join(DATA_DIR, f'{label}_latest.json')
    with open(latest_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info(f"JSON 已保存: {filepath}")
    return filepath


def save_to_csv(stocks: List[Dict], label: str = 'hot_stocks'):
    """保存为 CSV 文件"""
    os.makedirs(DATA_DIR, exist_ok=True)
    today = datetime.now(SHANGHAI).strftime('%Y%m%d')
    filepath = os.path.join(DATA_DIR, f'{label}_{today}.csv')

    if not stocks:
        logger.warning("无数据，CSV 未生成")
        return None

    fieldnames = [
        'rank', 'code', 'name', 'price', 'change_pct', 'source',
        'source_update_time', 'source_fetched_at', 'hot', 'description', 'collect_time',
    ]
    with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(stocks)

    logger.info(f"CSV 已保存: {filepath}")
    return filepath


def save_summary(stocks: List[Dict]):
    """保存汇总信息 JSON"""
    os.makedirs(DATA_DIR, exist_ok=True)
    today = datetime.now(SHANGHAI).strftime('%Y%m%d')

    summary = {
        'update_time': datetime.now(SHANGHAI).isoformat(),
        'date': today,
        'total': len(stocks),
        'top_gainers': sorted(stocks, key=lambda x: x['change_pct'], reverse=True)[:5],
        'top_rank': sorted(stocks, key=lambda x: x['rank'])[:10],
        'market_distribution': {
            'SH': len([s for s in stocks if s['code'].endswith('.SH')]),
            'SZ': len([s for s in stocks if s['code'].endswith('.SZ')])
        }
    }

    filepath = os.path.join(DATA_DIR, f'summary_{today}.json')
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    latest_path = os.path.join(DATA_DIR, 'summary_latest.json')
    with open(latest_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    logger.info(f"汇总已保存: {filepath}")


def main(config: dict = None):
    logger.info("=" * 50)
    logger.info("开始采集金融数据")
    logger.info(f"数据目录: {DATA_DIR}")

    stocks = collect_hot_stocks()

    if not stocks:
        logger.error("采集失败，未获取到任何股票")
        return {'success': False, 'message': '未获取到任何股票'}

    json_file = save_to_json(stocks)
    csv_file = save_to_csv(stocks)
    save_summary(stocks)

    result = {
        'success': True,
        'total': len(stocks),
        'json_file': json_file,
        'csv_file': csv_file
    }
    logger.info(f"采集完成: {len(stocks)} 只股票")
    logger.info("=" * 50)
    return result


if __name__ == "__main__":
    main()
