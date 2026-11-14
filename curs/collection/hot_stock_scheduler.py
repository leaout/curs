# coding: utf-8
"""Run the WhatsHot hot-stock sync after the A-share market closes."""
import logging
import threading
import time
from datetime import datetime, time as datetime_time
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
SHANGHAI = ZoneInfo('Asia/Shanghai')
START_AFTER = datetime_time(15, 35)
STOP_RETRY_AFTER = datetime_time(22, 0)
POLL_SECONDS = 30
RETRY_SECONDS = 15 * 60
EXPECTED_SOURCE = 'WhatsHot/同花顺网页'

_lock = threading.Lock()
_thread = None
_stop_event = None


def _sync_for_date(trade_date: str) -> bool:
    """Sync once and report success only when rows were persisted."""
    try:
        from curs.collection.hot_stocks import sync_hot_stocks_to_db
        from curs.database import get_db_manager

        result = sync_hot_stocks_to_db(get_db_manager(), category='hot', trade_date=trade_date)
        if not result.get('success'):
            logger.error('Automatic hot-stock sync failed for %s: %s', trade_date, result.get('message'))
            return False
        logger.info(
            'Automatic hot-stock sync completed for %s: %s/%s stocks, source=%s, fetched_at=%s',
            trade_date, result.get('success_count', 0), result.get('total', 0),
            result.get('source', 'unknown'), result.get('fetched_at', 'unknown'),
        )
        return True
    except Exception:
        logger.exception('Automatic hot-stock sync crashed for %s', trade_date)
        return False


def _run(stop_event: threading.Event) -> None:
    last_attempt_at = 0.0
    attempted_date = None
    while not stop_event.is_set():
        now = datetime.now(SHANGHAI)
        today = now.date().isoformat()

        if now.weekday() < 5 and now.time() >= START_AFTER and now.time() < STOP_RETRY_AFTER:
            try:
                from curs.database import get_db_manager
                db_manager = get_db_manager()
                latest = db_manager.get_last_trade_date()
                latest_source = db_manager.get_hot_stock_daily_source(today) if latest == today else None
            except Exception:
                latest = None
                latest_source = None
                logger.exception('Could not check most recent hot-stock sync date')

            if latest != today or latest_source != EXPECTED_SOURCE:
                monotonic_now = time.monotonic()
                if attempted_date != today or monotonic_now - last_attempt_at >= RETRY_SECONDS:
                    attempted_date = today
                    last_attempt_at = monotonic_now
                    if _sync_for_date(today):
                        # Database date check prevents a second sync after restart.
                        logger.info('Hot-stock daily sync is up to date for %s', today)
        elif now.time() >= STOP_RETRY_AFTER or now.weekday() >= 5:
            attempted_date = None
            last_attempt_at = 0.0

        stop_event.wait(POLL_SECONDS)


def start_hot_stock_scheduler() -> None:
    """Start a single daemon scheduler; safe to call during app initialization."""
    global _thread, _stop_event
    with _lock:
        if _thread and _thread.is_alive():
            return
        _stop_event = threading.Event()
        _thread = threading.Thread(
            target=_run, args=(_stop_event,), name='HotStockScheduler', daemon=True,
        )
        _thread.start()
    logger.info('Hot-stock scheduler started (weekdays after 15:35 Asia/Shanghai)')


def stop_hot_stock_scheduler() -> None:
    """Stop the scheduler during graceful service shutdown."""
    global _thread, _stop_event
    with _lock:
        stop_event = _stop_event
        thread = _thread
        _stop_event = None
        _thread = None
    if stop_event:
        stop_event.set()
    if thread and thread.is_alive():
        thread.join(timeout=2)
