# AGENTS.md - Curs Vibe Trading Development Guide

Curs is being rebuilt as a standalone multi-market Trading Agent. The V2 backend lives in `trading_v2/`; the React workspace lives in `web_v2/`.

## 1. Build, run, and test

### Backend

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-v2.txt
.\.venv\Scripts\python.exe -m trading_v2
.\.venv\Scripts\python.exe -m unittest discover -s test -p "test_trading_v2*.py" -v
```

The backend defaults to `127.0.0.1:8010`. Runtime settings use the `TRADING_V2_` environment prefix.

### Frontend

```powershell
cd web_v2
npm install
npm run dev
npm run build
```

The Vite development server defaults to port 5173 and proxies `/api` to the backend.

### Retained modules

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s test -v
```

Do not restore the removed Flask UI, `run.py`, `curs_main.py`, or the legacy service assembly.

## 2. Architecture boundaries

- `trading_v2/domain/` must not import FastAPI, database clients, provider SDKs, or legacy `curs` modules.
- V2 business services use explicit interfaces for market data, models, and brokers. Do not build a generic plugin system.
- Legacy `curs` code may only be imported by a V2 adapter.
- Reuse is limited to Eastmoney broker capabilities, market-data capabilities, database helpers, and data collection.
- A strategy is a persistent `TradingSession`; chat changes create immutable prompt and strategy versions.
- Local code evaluates bars and indicators. Invoke a model only for candidate signals.
- A model may produce structured decisions but may never call a broker directly.
- Deterministic risk checks and execution authorization are mandatory after every model decision.
- All important state transitions must be auditable and idempotent.
- The UI must clearly distinguish live, delayed, stale, and demo data.

## 3. Python style

- Add `# coding: utf-8` to Python files.
- Order imports as standard library, third party, then local modules.
- Use `snake_case` for functions and variables, `CamelCase` for classes, and `SCREAMING_SNAKE_CASE` for constants.
- Use type hints at public boundaries.
- Use `logging.getLogger(__name__)`; use `logger.exception()` when a stack trace is useful.
- Catch specific exceptions at provider boundaries. Never silently turn malformed data into a trading action.
- Require timezone-aware datetimes and normalize cross-system timestamps to UTC.
- Use `Decimal` for money and price domain values.
- Never log or return API keys, broker passwords, cookies, or full account credentials.

## 4. Frontend style

- Use React and TypeScript under `web_v2/`.
- Keep API access in `src/api/` and shared contracts in `src/types.ts`.
- The chart, chat, prompt versions, and event timeline must share stable correlation identifiers.
- Never display mock values as live values. Fallback data must show `DEMO DATA`.
- Keep the workspace usable on desktop and narrow screens.
- Run `npm run build` before committing frontend changes.

## 5. Configuration

- Commit examples only: `.env.v2.example` and `web_v2/.env.example`.
- Keep local secrets in ignored `.env`, `config.local.yml`, environment variables, or a secret manager.
- Broker configuration remains flat in `config.yml` under `eastmoney`.
- The default execution mode is `observe`.
- Live trading requires an account-level enable flag, healthy market data and broker connections, deterministic risk approval, and complete audit context.

## 6. Documentation

- Update `README.md` and `README_EN.md` together.
- Keep the cross-language links at the top of both files.
- Update the relevant documents in `docs/v2/` when domain contracts, APIs, or lifecycle rules change.

## 7. Git

- Show `git status` and the relevant diff before committing.
- Ask the user before committing unless the current user request already explicitly authorizes a commit.
- Do not push unless explicitly requested.
- Never commit generated `node_modules/`, `dist/`, local environments, session files, credentials, or runtime logs.
