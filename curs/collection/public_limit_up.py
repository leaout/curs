# coding: utf-8
"""Collect the daily public limit-up list without the QMT client."""

import logging
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from curs.database import get_db_manager

logger = logging.getLogger(__name__)


def collect_limit_up(trade_date=None):
    from curs.market_sentiment import fetch_cohort
    now = datetime.now(ZoneInfo('Asia/Shanghai'))
    if now.hour < 15:
        raise ValueError('Close snapshot collection is only allowed after 15:00 Shanghai time')
    trade_date = trade_date or datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d')
    compact_date = datetime.strptime(trade_date, '%Y-%m-%d').strftime('%Y%m%d')
    cohort = fetch_cohort(trade_date)
    get_db_manager().save_zt_snapshot(trade_date, cohort['members'], cohort['source'])
    codes = sorted(cohort['members'])
    # Keep the previous file on a holiday or empty upstream response.
    if not codes:
        logger.info('No daily limit-up list for %s; previous file preserved', trade_date)
        return 0
    data_dir = Path(__file__).resolve().parents[2] / 'data'
    data_dir.mkdir(parents=True, exist_ok=True)
    content = ''.join(code + '\n' for code in codes)
    (data_dir / f'zt_list_{compact_date}.txt').write_text(content, encoding='utf-8')
    (data_dir / 'zt_list_pre.txt').write_text(content, encoding='utf-8')
    logger.info('Public daily limit-up list saved: %s, %s stocks', trade_date, len(codes))
    return len(codes)


def main():
    logging.basicConfig(level=logging.INFO)
    for attempt in range(3):
        try:
            collect_limit_up()
            return
        except Exception:
            logger.exception('Daily public limit-up collection failed (attempt %s/3)', attempt + 1)
            if attempt < 2:
                time.sleep(5)
    raise SystemExit(1)


if __name__ == '__main__':
    main()
