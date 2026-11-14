# Curs

Curs is a personal A-share research and signal-recording platform. The current default is **signal-only**: it does not connect to a live brokerage account or place orders.

[中文版](README.md)

## Current features

- Uses public Tencent quotes to produce and record observations from the existing strategies.
- Collects the Tonghuashun hot-stock ranking shown on WhatsHot and displays its source and fetch time in the stock-pool page.
- Stores daily hot-stock snapshots and end-of-day limit-up records for market-sentiment and historical research pages.
- Includes hot-stock research, optional WorkBuddy Desktop Bridge analysis, market-sentiment monitoring, forward signal observations, and a shadow relay monitor.

## Hot-stock collection

Curs renders WhatsHot's public Tonghuashun ranking with local Chrome. No API key is required, and Curs does not request Tonghuashun directly. The web service syncs on weekdays after 15:35 China Standard Time, retries every 15 minutes until 22:00, and also provides a manual sync action under **Manage → Stock Pool**. The GitHub Actions daily collection and archive-import workflow has been removed.

Chrome must be installed on the host, and the Windows account running Curs must be able to launch it. If Chrome is not detected automatically, set its path in `config.local.yml`:

```yaml
whatshot:
  chrome_path: "C:/Program Files/Google/Chrome/Application/chrome.exe"
```

If the page is unavailable, its structure changes, or no valid stock rows are found, collection fails and retries; a stale cache is never presented as today's ranking. The page does not provide a reliable live trade price. See the [WhatsHot integration and troubleshooting guide](docs/WHATSHOT_INTEGRATION.md) for source and data limitations.

## Install and run

Requires Python 3.10+, a reachable PostgreSQL database, and Chrome.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

Open <http://localhost:5000>. Daily hot-stock collection starts with the web service. `--engine-only` does not start the collector; `--web-only` runs the pages and hot-stock sync.

## Configuration

Put database credentials and machine-specific paths in the untracked `config.local.yml`. Defaults for quotes and WhatsHot are in `config.yml`. At minimum, configure PostgreSQL:

```yaml
database:
  host: 127.0.0.1
  port: 5432
  database: postgres
  user: postgres
  password: "change-me"
```

Ensure PostgreSQL is reachable and the required project tables exist. Service logs are written to `logs/`. Never commit database passwords, account credentials, login sessions, or local runtime data.

## Runtime boundaries

- `signal_only: true` and `broker: signal` are the defaults. A signal is not an order or a confirmed fill.
- Public quote and WhatsHot sources have no availability guarantee; source or page changes may interrupt collection.
- The after-close collection requires the service to remain running. It cannot run while the host is asleep or the service is stopped.
- WorkBuddy analysis is optional and requires a reachable local Desktop Bridge; it is independent of hot-stock sync.

## Design and operations guides

- [WhatsHot hot-stock integration and troubleshooting](docs/WHATSHOT_INTEGRATION.md)
- [Hot-stock agent research](docs/STOCK_INTELLIGENCE.md)
- [Signal-only mode, quotes, and deployment](docs/SIGNAL_ONLY.md)
- [Limit-up relay observation](docs/RELAY_V1.md)
- [KOL evidence integration rules](docs/KOL_RELAY.md)
- [Signal opportunity counting](docs/OPPORTUNITIES.md)
- [Code review notes](docs/REVIEW_20261014.md)
