# AGENTS.md - Development Guide for Curs

Curs is a personal automated quantitative investment platform written in Python.

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
# 使用统一入口启动（推荐）
python run.py                    # 启动所有服务
python run.py --help             # 查看帮助

# 单独启动
python run.py --web-only         # 仅Web服务
python run.py --engine-only      # 仅交易引擎

# 指定端口
python run.py -p 8080            # Web端口8080
```

### Legacy (deprecated)
```bash
python curs_main.py              # 旧入口（包含引擎+API）
python web/app.py               # 旧Web入口
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

### Logging
- Use `logging.getLogger(__name__)` to create module-level loggers
- Log levels: `logger.debug()`, `logger.info()`, `logger.warning()`, `logger.error()`, `logger.exception()`

### File Structure
```
curs/
├── core/           # Core engine and scheduling
├── strategy/       # Strategy loading and execution
├── broker/         # Trading broker integration (QMT)
├── data_source/    # Historical data handling
├── collection/     # Data collection modules
├── log_handler/    # Logging configuration
├── utils/          # Utility functions
├── api/            # API endpoints
└── train/          # Training modules
```

### Key Dependencies
- pandas, numpy - data processing
- pytdx - market data retrieval
- backtrader - backtesting
- Flask - web interface
- psycopg2-binary - PostgreSQL database
- requests, aiohttp - HTTP operations
- pyyaml - configuration parsing

### Configuration
- Application configuration in `config.yml`
- Use `load_yaml()` from `curs.utils.config` to load configs

### Strategy Development
- Strategies define functions: `init`, `before_trading`, `handle_bar`, `handle_tick`, `after_trading`
- Access market data through the event bus system
- Use `context` object to store strategy state

### Testing Notes
- Test files located in `test/` directory
- No formal test framework configured (pytest.ini not present)
- Use unittest-style test functions
- Tests can use `eval()` for expression evaluation testing

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
