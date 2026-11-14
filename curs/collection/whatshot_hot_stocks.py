# coding: utf-8
"""Scrape the public WhatsHot Tonghuashun hot-stock page with headless Chrome."""
import logging
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from curs.utils.config import load_yaml

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PAGE_URL = 'https://whatshot.top/news/ths-10jqka?type=hot-stock&view=detail'
DEFAULT_LIMIT = 100
DEFAULT_RENDER_WAIT_MS = 12000
DEFAULT_TIMEOUT_SECONDS = 45


class _HotStockPageParser(HTMLParser):
    """Extract rendered stock rows without depending on third-party parsers."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.items: List[Dict] = []
        self.current: Optional[Dict] = None
        self.row_depth = 0
        self.tag_stack: List[Dict] = []
        self.active_captures: List[Dict] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        attributes = dict(attrs)
        classes = set((attributes.get('class') or '').split())

        if self.current is None and tag == 'li' and 'rank-item' in classes:
            self.current = {'rank_text': [], 'name_text': [], 'summary_text': [], 'url': ''}
            self.row_depth = 1
        elif self.current is not None and tag == 'li':
            self.row_depth += 1

        frame = {'tag': tag, 'captures': []}
        if self.current is not None:
            if tag == 'span' and 'rank-index' in classes:
                frame['captures'].append(self.current['rank_text'])
            if tag == 'a' and 'rank-title' in classes:
                frame['captures'].append(self.current['name_text'])
                self.current['url'] = attributes.get('href') or ''
            if tag == 'div' and 'rank-content' in classes:
                frame['captures'].append(self.current['summary_text'])
            self.active_captures.extend(frame['captures'])
        self.tag_stack.append(frame)

    def handle_startendtag(self, tag: str, attrs) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        if not data or self.current is None:
            return
        for capture in self.active_captures:
            capture.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.current is None:
            return

        for index in range(len(self.tag_stack) - 1, -1, -1):
            if self.tag_stack[index]['tag'] == tag:
                removed = self.tag_stack[index:]
                del self.tag_stack[index:]
                for frame in removed:
                    for capture in frame['captures']:
                        for capture_index in range(len(self.active_captures) - 1, -1, -1):
                            if self.active_captures[capture_index] is capture:
                                del self.active_captures[capture_index]
                                break
                break

        if tag == 'li':
            self.row_depth -= 1
            if self.row_depth <= 0:
                self._finish_row()

    def _finish_row(self) -> None:
        row = self.current
        self.current = None
        self.row_depth = 0
        self.tag_stack.clear()
        self.active_captures.clear()
        if not row:
            return

        name = ''.join(row['name_text']).strip()
        code_match = re.search(r'(?:stockpage\.10jqka\.com\.cn/|/)(\d{6})(?:/|$)', row['url'])
        if not name or not code_match:
            return

        code = _normalize_code(code_match.group(1))
        if not code:
            return

        rank = len(self.items) + 1
        rank_text = ''.join(row['rank_text'])
        rank_prefix = '{:02d}'.format(rank) if rank < 100 else str(rank)
        hot_text = rank_text[len(rank_prefix):].strip() if rank_text.startswith(rank_prefix) else ''
        summary = ' '.join(''.join(row['summary_text']).split())
        if summary.startswith(name):
            summary = summary[len(name):].lstrip(' ：:·|')

        self.items.append({
            'code': code,
            'name': name,
            'rank': rank,
            'hot': _parse_heat(hot_text),
            'description': summary,
            'change_pct': _parse_change_pct(summary),
        })


def _settings() -> dict:
    config_path = PROJECT_ROOT / 'config.yml'
    config = load_yaml(str(config_path)) or {}
    settings = config.get('whatshot', {}) or {}
    try:
        limit = int(settings.get('limit', DEFAULT_LIMIT))
    except (TypeError, ValueError):
        limit = DEFAULT_LIMIT
    try:
        render_wait_ms = int(settings.get('render_wait_ms', DEFAULT_RENDER_WAIT_MS))
    except (TypeError, ValueError):
        render_wait_ms = DEFAULT_RENDER_WAIT_MS
    try:
        timeout_seconds = int(settings.get('timeout_seconds', DEFAULT_TIMEOUT_SECONDS))
    except (TypeError, ValueError):
        timeout_seconds = DEFAULT_TIMEOUT_SECONDS

    return {
        'page_url': os.environ.get('WHATSHOT_PAGE_URL') or settings.get('page_url') or DEFAULT_PAGE_URL,
        'chrome_path': os.environ.get('WHATSHOT_CHROME_PATH') or settings.get('chrome_path') or '',
        'limit': min(max(limit, 1), DEFAULT_LIMIT),
        'render_wait_ms': min(max(render_wait_ms, 1000), 30000),
        'timeout_seconds': min(max(timeout_seconds, 10), 120),
    }


def _find_chrome(configured_path: str = '') -> str:
    candidates = [configured_path, shutil.which('chrome'), shutil.which('google-chrome'), shutil.which('chromium')]
    if os.name == 'nt':
        local_app_data = os.environ.get('LOCALAPPDATA', '')
        program_files = os.environ.get('PROGRAMFILES', r'C:\Program Files')
        program_files_x86 = os.environ.get('PROGRAMFILES(X86)', r'C:\Program Files (x86)')
        candidates.extend([
            os.path.join(local_app_data, 'Google', 'Chrome', 'Application', 'chrome.exe'),
            os.path.join(local_app_data, 'Google', 'Chrome', 'Bin', 'chrome.exe'),
            os.path.join(program_files, 'Google', 'Chrome', 'Application', 'chrome.exe'),
            os.path.join(program_files_x86, 'Google', 'Chrome', 'Application', 'chrome.exe'),
        ])
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return candidate
    raise FileNotFoundError(
        'Google Chrome was not found. Install Chrome or set WHATSHOT_CHROME_PATH to chrome.exe.'
    )


def _normalize_code(raw_code: object) -> str:
    code = str(raw_code or '').strip().upper()
    match = re.fullmatch(r'(\d{6})(?:\.(SH|SZ|BJ))?', code)
    if not match:
        return ''
    number, exchange = match.groups()
    if not exchange:
        if number.startswith(('4', '8', '92')):
            exchange = 'BJ'
        elif number.startswith('6'):
            exchange = 'SH'
        else:
            exchange = 'SZ'
    return '{}.{}'.format(number, exchange)


def _parse_change_pct(description: object) -> float:
    match = re.search(r'(?:涨跌幅|涨幅)\s*[：:]\s*([+-]?\d+(?:\.\d+)?)\s*%', str(description or ''))
    return float(match.group(1)) if match else 0.0


def _parse_heat(raw_heat: str):
    match = re.search(r'([\d.]+)\s*(万|亿)?', str(raw_heat or ''))
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2)
    if unit == '万':
        value *= 10000
    elif unit == '亿':
        value *= 100000000
    return int(value) if value.is_integer() else value


def _page_update_time(page_html: str, fetched_at: datetime) -> datetime:
    match = re.search(r'(\d{1,3})\s*分钟前更新', page_html)
    if match:
        return fetched_at - timedelta(minutes=int(match.group(1)))
    if '刚刚更新' in page_html:
        return fetched_at
    return fetched_at


def _render_public_page(settings: dict) -> str:
    chrome = _find_chrome(str(settings.get('chrome_path') or ''))
    with tempfile.TemporaryDirectory(prefix='curs_whatshot_') as profile_dir:
        command = [
            chrome,
            '--headless=new',
            '--disable-gpu',
            '--disable-background-networking',
            '--disable-sync',
            '--no-first-run',
            '--no-default-browser-check',
            '--virtual-time-budget={}'.format(settings['render_wait_ms']),
            '--user-data-dir={}'.format(profile_dir),
            '--dump-dom',
            settings['page_url'],
        ]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=settings['timeout_seconds'],
            check=False,
        )
    if result.returncode != 0:
        error = result.stderr.strip().splitlines()[-1:] or ['unknown Chrome error']
        raise RuntimeError('Chrome page render failed: {}'.format(error[0]))
    return result.stdout


def get_whatshot_hot_stocks() -> List[Dict]:
    """Scrape the public rendered WhatsHot Tonghuashun ranking without an API key."""
    settings = _settings()
    fetched_at = datetime.now(ZoneInfo('Asia/Shanghai'))
    try:
        page_html = _render_public_page(settings)
        if '正在校验访问' in page_html or '访问验证' in page_html:
            raise RuntimeError('WhatsHot returned its access-check page instead of the public ranking')

        parser = _HotStockPageParser()
        parser.feed(page_html)
        stocks = parser.items[:settings['limit']]
        if not stocks:
            raise ValueError('WhatsHot page rendered no valid A-share hot-stock rows')

        update_time = _page_update_time(page_html, fetched_at)
        for stock in stocks:
            stock.update({
                'price': 0,
                'source': 'WhatsHot/同花顺网页',
                'source_update_time': update_time.strftime('%Y-%m-%d %H:%M:%S'),
                'source_fetched_at': fetched_at.strftime('%Y-%m-%d %H:%M:%S'),
            })

        logger.info(
            'Scraped %s Tonghuashun hot stocks from WhatsHot page; page update time: %s',
            len(stocks), update_time.strftime('%Y-%m-%d %H:%M:%S'),
        )
        return stocks
    except (OSError, subprocess.SubprocessError, ValueError, RuntimeError, TypeError) as exc:
        logger.warning('Scraping WhatsHot Tonghuashun ranking failed: %s', exc)
        return []
