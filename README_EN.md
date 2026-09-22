# Curs Vibe Trading

[中文版](README.md) | English Version

Curs is being rebuilt as a multi-market Trading Agent. Each strategy is a long-lived model conversation session: users create and revise strategies through chat, while signals, model decisions, risk checks, and order events appear on the chart and audit timeline.

The legacy Flask UI, `run.py` service entry point, and first-generation service assembly have been removed. V2 is isolated from the old architecture and retains only broker, market-data, database, and collection capabilities that can be migrated behind adapters.

## Current milestone

Implemented:

- A standalone FastAPI V2 control plane with health checks, OpenAPI, and a bounded SSE event stream.
- Cross-market domain models for China equities, US equities, crypto, and FX.
- Foundations for `observe / paper / live` modes and typed signal, decision, and order states.
- A React + TypeScript workspace with sessions, candlesticks, signal overlays, chat, prompt versions, and a decision timeline.
- A cpptdx HTTP adapter for China-equity snapshots, minute bars, health checks, and freshness tracking.
- An explicit `DEMO DATA` state when cpptdx is unavailable. Unconfigured brokers and models are never shown as connected.
- Durable strategy sessions, chat messages, and append-only prompt/strategy versions. SQLite is the development default; PostgreSQL is supported for production.
- Model adapters for OpenAI, DeepSeek, Claude, and OpenAI-compatible APIs. API keys are only read from environment variables.
- One-sentence strategy creation compiled into a strict allowlisted JSON schema. Missing model configuration or invalid output remains a safe draft.
- The Web workspace now uses the real Session API for creation, chat revisions, version history, pause, and resume.

Not implemented yet:

- Paper Broker, QMT/Eastmoney V2 broker adapters, and live order execution.
- QMT as the real-time primary feed with cpptdx failover.
- Closed-bar indicators, candidate signals, model trading decisions, deterministic risk checks, and persistent audit events.

This version is for architecture and UI integration. It must not be used for live automated trading.

## Repository layout

```text
trading_v2/       # Standalone FastAPI, domain models, events, market APIs
web_v2/           # React + TypeScript Vibe Trading workspace
docs/v2/          # Architecture, data model, API, and lifecycle documents
curs/broker/      # Retained QMT and Eastmoney broker capabilities
curs/collection/  # Retained data collection capabilities
data_collection/  # Daily hot-stock collection and import
test/             # V2 and retained-module tests
```

## Installation

Backend:

```powershell
cd E:\pro\curs-trading-agent
.\.venv\Scripts\python.exe -m pip install -r requirements-v2.txt
Copy-Item .env.v2.example .env
```

Frontend:

```powershell
cd E:\pro\curs-trading-agent\web_v2
npm install
```

Keep secrets in `config.local.yml`, environment variables, or a secret manager. Never commit API keys, broker passwords, or session files.

## Running

Start the V2 backend:

```powershell
cd E:\pro\curs-trading-agent
.\.venv\Scripts\python.exe -m trading_v2
```

Default endpoints:

- API: `http://127.0.0.1:8010/api/v2`
- OpenAPI: `http://127.0.0.1:8010/docs`
- cpptdx: `http://127.0.0.1:8022`

Start the V2 frontend:

```powershell
cd E:\pro\curs-trading-agent\web_v2
npm run dev
```

Open `http://127.0.0.1:5173`. Vite proxies `/api` to port 8010.

## Database and strategy sessions

Without database configuration, the service uses `data/trading_v2.db` and runs immediately. PostgreSQL is recommended in production:

```dotenv
TRADING_V2_DATABASE_URL=postgresql+psycopg2://user:password@127.0.0.1:5432/curs_trading
```

The service currently creates `trading_sessions_v2`, `trading_messages_v2`, and `trading_prompt_versions_v2` automatically. Schema migrations will be added before live trading is enabled.

## Model configuration

DeepSeek:

```dotenv
TRADING_V2_MODEL_ENABLED=true
TRADING_V2_MODEL_PROVIDER=deepseek
TRADING_V2_MODEL_NAME=deepseek-chat
TRADING_V2_MODEL_API_KEY_ENV=DEEPSEEK_API_KEY
DEEPSEEK_API_KEY=your-secret
```

For OpenAI, use `openai / gpt-5` with `OPENAI_API_KEY`. For Claude, use `anthropic / claude-sonnet-4-5` with `ANTHROPIC_API_KEY`. For a compatible Chat Completions service, select `openai_compatible` and set `TRADING_V2_MODEL_BASE_URL`.

The model only compiles conversation input into a constrained strategy representation. It has no broker, order, or publication authority. Every new strategy currently stays in draft/observe mode.

## cpptdx

Configure it through `.env`:

```dotenv
TRADING_V2_CPPTDX_BASE_URL=http://127.0.0.1:8022
TRADING_V2_CPPTDX_TIMEOUT_SECONDS=3
```

Available endpoints:

- `GET /api/v2/market/status`
- `GET /api/v2/market/bars?instrument=cn_equity:XSHG:600000&timeframe=5m&limit=200`
- `POST /api/v2/market/snapshots`

cpptdx is used for China-equity minute bars, snapshots, and gap filling. It does not execute broker orders.

## Broker configuration

Retained QMT and Eastmoney code lives under `curs/broker/`. V2 adapters are not wired yet, so configuring a broker does not grant V2 order authority.

Example:

```yaml
broker: qmt

qmt:
  path: ""
  account_id: ""
  trader_name: ""

eastmoney:
  account_no: ""
  password: ""
  session_file: "data/eastmoney_trader.session"
```

Eastmoney depends on a web trading interface and may break when its API or login checks change. Begin with a read-only connection test, then validate with paper or approval mode.

## Tests

```powershell
# V2
.\.venv\Scripts\python.exe -m unittest discover -s test -p "test_trading_v2*.py" -v

# Frontend production build
cd web_v2
npm run build
```

## Documentation

- [V2 architecture](docs/v2/ARCHITECTURE.md)
- [V2 data model](docs/v2/DATA_MODEL.md)
- [V2 API](docs/v2/API.md)
- [V2 trading lifecycle](docs/v2/TRADING_LIFECYCLE.md)
- [中文文档](README.md)
