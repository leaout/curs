# Curs

### An A-share market research and strategy signal desk

Bring market themes, public quotes, strategy signals, and AI-assisted research into one workspace for a clearer view of the trading day.

**Current mode: research and signal recording only. No live brokerage connection or automatic order execution.**

[中文版](README.md) · [Quick Start](#quick-start) · [Documentation](#documentation)

## What you can do

### Follow market themes

View the Tonghuashun hot-stock ranking published on WhatsHot, see each stock's data source and collection time, and keep daily snapshots for later research.

### Observe strategy signals

Run existing A-share strategies with public market data and review signals, trigger context, and subsequent price observations in one place. Signals are for research and are not orders or confirmed fills.

### Read market sentiment

Use market breadth, limit-up records, and consecutive limit-up ladders to follow the market environment and theme continuation.

### Research individual stocks with an agent

Open a hot stock's research view and optionally use the local WorkBuddy Desktop Bridge to produce an AI-assisted analysis.

## Quick Start

Requirements: Python 3.10+, PostgreSQL, and Chrome available to the account running Curs.

```powershell
git clone https://github.com/leaout/curs.git
cd curs
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create `config.local.yml` in the project root and enter your database connection:

```yaml
database:
  host: 127.0.0.1
  port: 5432
  database: postgres
  user: postgres
  password: "your-database-password"
```

Start the service and open <http://localhost:5000>:

```powershell
python run.py
```

If the service account cannot locate Chrome automatically, add `whatshot.chrome_path` to the same local config. See the [WhatsHot integration guide](docs/WHATSHOT_INTEGRATION.md) and [signal-only deployment guide](docs/SIGNAL_ONLY.md) for setup and troubleshooting.

## Documentation

- [Hot-stock agent research](docs/STOCK_INTELLIGENCE.md)
- [WhatsHot ranking integration](docs/WHATSHOT_INTEGRATION.md)
- [Signal mode, market data, and deployment](docs/SIGNAL_ONLY.md)
- [Limit-up relay observation](docs/RELAY_V1.md)
- [KOL evidence integration rules](docs/KOL_RELAY.md)
- [Signal opportunity counting](docs/OPPORTUNITIES.md)

## Data and use

Quotes and rankings come from public data sources; source or page changes can affect availability and completeness. Strategy signals and agent analysis are research tools, not investment advice or a promise of returns. This project currently does not execute live trades.
