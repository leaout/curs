# AGENTS.md - Development Guide for Curs

Curs is a personal automated quantitative investment platform written in Python, specializing in limit-up stock trading strategies.

## 1. Build & Test Commands

### Installation
```bash
pip install -r requirements.txt
python setup.py install
```

### Running Tests
```bash
# Run all tests
python -m unittest discover -s test

# Run a single test file
python -m unittest test.curs_test

# Run a specific test function
python -m unittest test.curs_test.test_eval
```

### Running the Application
```bash
# Use unified entry point (recommended)
python run.py                    # Start all services
python run.py --help            # View help

# Start individually
python run.py --web-only       # Web service only
python run.py --engine-only     # Trading engine only

# Specify port
python run.py -p 8080          # Web port 8080
```

### Legacy (deprecated)
```bash
python curs_main.py              # Old entry (includes engine+API)
python web/app.py               # Old Web entry
```

## 2. Code Style Guidelines

### Encoding
- Always use `# coding: utf-8` at the top of all Python files

### Import Conventions
- Standard library imports first
- Third-party imports second
- Local/curs module imports last
- Group imports by type with blank lines between groups
```python
import os
import sys
import subprocess
import signal
import argparse
import time

from flask import Flask, render_template, request, jsonify
import threading
import json
import csv
import logging
import math

from curs.core.engine import Engine
from curs.utils.config import load_yaml
from curs.cursglobal import *
from curs.strategy import *
```

### Naming Conventions
- **Variables/Functions**: snake_case (e.g., `check_and_start_qmt`, `connection_success`)
- **Classes**: CamelCase (e.g., `Strategy`, `Engine`, `QmtStockAccount`)
- **Constants**: SCREAMING_SNAKE_CASE
- **Private members**: prefix with `_` (e.g., `_user_context`, `_init`)

### Type Hints
- Use type hints for function parameters and return types where beneficial
```python
def create_data_dir() -> str:
def __init__(self, event_bus, scope, ucontext):
```

### Error Handling
- Use Python's built-in logging for error reporting
- Use `try/except` blocks with specific exception types when possible
- Always log exceptions with `logger.exception()` for stack traces
- **Critical**: Wrap strategy functions with try-except to prevent service crashes:
```python
def handle_tick(context, ticks):
    try:
        _handle_tick_inner(context, ticks)
    except Exception as e:
        logger.error(f"处理tick异常: {e}", exc_info=True)
```

### Logging
- Use `logging.getLogger(__name__)` to create module-level loggers
- Log levels: `logger.debug()`, `logger.info()`, `logger.warning()`, `logger.error()`, `logger.exception()`
- Log files stored in `logs/` directory with 5-day rotation
- Simplified format: `"%(asctime)s %(levelname)s - %(message)s"`

### File Structure
```
curs/
├── core/           # Core engine and scheduling
├── strategy/       # Strategy loading and execution
├── broker/         # Trading broker integration (QMT)
│   ├── qmt_account.py    # QMT account management
│   ├── qmt_quote.py      # QMT quote engine
│   ├── order_tracker.py  # Order status tracking
│   ├── profit_stats.py   # Profit statistics
│   └── optimized_quote.py # Optimized quote engine
├── data_source/    # Historical data handling
├── collection/     # Data collection modules (hot_stocks.py)
├── log_handler/    # Logging configuration
├── utils/         # Utility functions
├── api/            # API endpoints
└── train/         # Training modules
```

### Key Dependencies
- pandas, numpy - data processing
- pytdx, xtquant - market data retrieval and trading
- Flask - web interface
- psycopg2-binary - PostgreSQL database
- requests, aiohttp - HTTP operations
- pyyaml - configuration parsing
- akshare - financial data APIs

### Configuration
- Application configuration in `config.yml` or `config.local.yml`
- Config structure uses flat keys (e.g., `config["qmt"]["path"]`)
- **NOT** nested under `base.accounts`
```python
# Correct
qmt_config = config.get("qmt", {})
qmt_path = qmt_config.get("path", "")

# Wrong (old style)
qmt_path = config["base"]["accounts"]["qmt_path"]
```

### Strategy Development
- Strategies define functions: `init`, `before_trading`, `handle_tick`, `after_trading`
- Access market data through the event bus system
- Use `context` object to store strategy state
- **T+1 Trading**: A-share stocks cannot be sold on the same day they are bought
- **Order Tracking**: Use `OrderTracker` class to track order status

### Database
- Use `get_db_manager()` to get database manager instance
- Tables: `strategy_signals`, `stock_pool`, `stock_info`, `profit_stats`, `zt_stocks`
- Handle `None` returns from `execute_query()` gracefully

## 3. Documentation Rules

### README Maintenance
- Always update **both** `README.md` (Chinese) and `README_EN.md` (English) together
- When one is modified, the other should be updated to match
- Add cross-language links at the top: `[English Version](README_EN.md)` in Chinese, `[中文版](README.md)` in English
- Add Documentation section at the bottom linking to both versions

### Git Commit Rules
- **Always ask user before committing** - Never auto-commit
- Show changes with `git status` and `git diff` first
- Get user confirmation before executing commit
- Do not push to remote unless explicitly requested
