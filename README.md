# Quant Lab

Quant Lab is a local Python and Dash quantitative research platform for market visualization, historical replay, strategy scripting, backtesting, walk-forward validation, paper-trading simulation, structured market research, and experiment management.

> **Research and simulation only.** The research, Auto Lab, walk-forward, and paper-review workflows do not place live broker orders. This project is not financial advice and is not production trading infrastructure.

## Current Application

The main application runs from `Live/app.py` and provides one browser-based workspace with these tabs:

- **Dashboard**: live or cached market charting, symbol/timeframe controls, quote metrics, and compact session statistics.
- **Watch**: live/replay charting, single-day and range loading, replay controls, strategy overlays, backtests, paper trading, and trade analytics.
- **Newsroom**: source-routed research, official-source evidence, SEC/FRED/BLS integrations, result-quality checks, structured evidence, and strategy-context handoff.
- **AI Auto Lab**: symbol discovery, multi-symbol Universe testing, strategy mutation/ranking, walk-forward and stress validation, progress tracking, run reports, and manual paper-review activation.
- **Settings**: market-data, AI/provider, runtime, and application configuration diagnostics.
- **Data Library**: artifact scanning, catalog search, metadata filtering, previews, ingestion, and database status.
- **Quant Dashboard**: quantitative experiment, strategy, backtest, walk-forward, universe, feature, risk, and data-quality views, plus a simulation-only Research Loop launcher.

Data Library and Quant Dashboard are attached to the main Dash tab layout during application startup.

## Major Features

### Market Data and Replay

- Interactive Brokers integration through `ib_async` for live snapshots and historical data.
- Local CSV/cache-backed operation when suitable data already exists.
- Single-session and multi-day replay with play, pause, step, rewind, seek, and speed controls.
- Background replay-range jobs with progress reporting and concurrency limits.
- Timeframe-aware replay routing and range safety policies.
- Replay cache validation for incomplete, stale, holiday, and partial-session data.
- Chart rendering separated from frequently changing metrics to reduce callback and browser pressure.

### Strategy Lab and Backtesting

- Pine Script-inspired strategy language implemented by the local strategy engine.
- Indicators including SMA, EMA, RSI, ATR, highest/lowest, crossover, and crossunder.
- Boolean expressions, comparisons, time/session filters, buy/sell rules, plots, and background regimes.
- Strategy overlays, trade markers, and paper-trading visualization on Watch charts.
- Backtests with PnL, return, win rate, drawdown, trade, fee, slippage, and equity analytics.
- Strategy AI context packets and research-aware advisor handoff.

Example:

```text
fast = ta.ema(close, 9)
slow = ta.ema(close, 21)

plot fast
plot slow

buy when ta.crossover(fast, slow)
sell when ta.crossunder(fast, slow)
```

See `Live/docs/STRATEGY_LANGUAGE.md` for the language reference.

### AI Auto Lab

Auto Lab is an automated, simulation-only research workflow built around the existing strategy and backtest engines.

- **Symbol Explorer** keeps user seed symbols and rotates through peer- and theme-relevant exploration candidates.
- **Universe Auto Lab** evaluates strategy families and mutations across multiple symbols.
- Candidate ranking uses normalized scorecards, objective progress, return, Sharpe-related metrics, drawdown, and robustness across symbols.
- Capital controls support configurable starting cash, target cash, sizing mode, cash exposure, and fixed quantity assumptions.
- **Walk-Forward Validation** consumes the exact candidate packet produced by the associated Universe run.
- Validation separates training, unseen testing, rolling windows, fee/slippage stress, and a final untouched holdout.
- Exact-result caching includes candidate-packet identity to avoid stale or cross-run strategy reuse.
- Background jobs expose progress, stage, completion state, and human-readable reports without requiring a second terminal.
- Run manifests preserve exact report, script, candidate-packet, and Paper Review associations.
- **Paper Review** is manual-only: promoted candidates can be reviewed and activated as visual strategy simulations in the Paper Trading workspace.
- Market Memory packets provide reusable research context between Auto Lab workflows.

### Research and Newsroom

- Query planning and source routing based on the research topic.
- Trusted-source registry and source-quality scoring.
- SEC Company Facts parsing and official SEC source adapters.
- FRED and BLS macroeconomic evidence adapters.
- Evidence hydration, coverage checks, quality gates, relevance validation, and result hygiene.
- Structured research briefs and evidence packets.
- Newsroom-to-Research-Analyst and Newsroom-to-Strategy-AI context bridges.

### Data Library and Persistence

- Artifact registry for generated JSON, CSV, Markdown, reports, and research outputs.
- Searchable Data Library with artifact previews and ingestion status.
- SQLite is the default local database backend.
- PostgreSQL is optional and uses centralized configuration and connection management.
- Automated schema migrations support both database backends.
- Typed quantitative schema includes symbols, experiments, strategy runs, backtests, walk-forward runs, universe runs, feature snapshots, risk snapshots, model candidates, and data-quality events.
- Quant Dashboard provides read-only views over normalized research and experiment records; its explicit **Run Research Loop** action generates candidates and persists a new simulation result.

### Research Loop

- Simulation-only candidate generation and evaluation pipeline.
- Strategy candidate generation, bar adapters, backtest adapters, scoring, and memory feedback.
- Persisted experiment/result capture through the quantitative schema.
- No broker calls or live-order placement.

## Technology

- Python 3.10+
- Dash and Plotly
- pandas and pandas-ta
- `ib_async`
- SQLite
- PostgreSQL with optional `psycopg`
- yfinance for supported fallback/research data paths
- HTML and CSS

## Repository Layout

Most generated data, caches, exports, local environments, and IDE metadata are omitted. The two expected local symbol filenames are shown for setup clarity.

```text
AlgoTrader/
|-- .env.example                 # Optional database environment template
|-- .gitignore                   # Local data, secrets, caches, and IDE exclusions
|-- README.md
|-- scripts/                     # PostgreSQL setup/status PowerShell helpers
|-- docs/                        # Repository-level notes and supporting documents
`-- Live/
    |-- app.py                   # Main Dash application and dynamic tab integration
    |-- callbacks.py             # Dashboard, Watch, replay, strategy, and paper callbacks
    |-- config.py                # Application defaults and symbol/timeframe configuration
    |-- assets/                  # Dash CSS and browser-side assets
    |-- core/
    |   |-- RealTime.py          # IBKR market-data adapter
    |   |-- ReplayModule.py      # Replay engine
    |   |-- StrategyEngine.py    # Strategy parser and signal engine
    |   |-- BackTestEngine.py    # Backtesting engine
    |   |-- IndicatorEngine.py   # Indicator calculations
    |   |-- PaperBroker.py       # Local simulated broker
    |   `-- RiskGuard.py         # Paper/research risk controls
    |-- renderers/               # Watch chart and strategy overlay rendering
    |-- models/                  # Shared UI/domain models
    |-- ui/
    |   |-- tabs_ui.py           # Dashboard, Watch, Strategy, Paper, and Analytics layouts
    |   |-- newsroom_ui.py       # Newsroom and evidence interface
    |   |-- auto_lab_ui.py       # AI Auto Lab interface
    |   |-- data_library_ui.py   # Data Library interface
    |   |-- settings_ui.py       # Settings interface
    |   `-- research_autolab_ui.py
    |-- services/
    |   |-- ai/                  # AI provider and Auto Lab orchestration
    |   |   `-- auto_lab_orchestrator/
    |   |       |-- symbol_discovery.py
    |   |       |-- universe_runner.py
    |   |       |-- walk_forward_runner.py
    |   |       |-- orchestrator.py
    |   |       |-- mutator.py
    |   |       |-- scorecard.py
    |   |       `-- *_self_test.py
    |   |-- replay/              # Range jobs, safety policy, and timeframe routing
    |   |-- research/            # Newsroom sources, evidence, and analyst workflows
    |   |-- research_loop/       # Automated candidate/evaluation loop
    |   |-- data_catalog/        # Artifact scanning, catalog, preview, and ingestion
    |   |-- database/            # SQLite/PostgreSQL backend and migrations
    |   |-- quant_schema/        # Typed experiment persistence and repositories
    |   |-- quant_dashboard/     # Quant Dashboard queries, callbacks, and UI
    |   |-- artifacts/           # Managed artifact registry/writers
    |   |-- market_data/         # Provider-based market-data services
    |   |-- market_calendar/     # Trading-session/calendar helpers
    |   |-- config/              # Provider and credential configuration
    |   |-- llm/                 # LLM provider abstractions
    |   |-- watch/               # Watch workspace services
    |   `-- safety/              # Research and execution safety boundaries
    |-- data/                    # Generated/local data (gitignored)
    |   |-- nasdaq_tickers_simple.txt      # Local symbol list when installed
    |   `-- nasdaq_symbol_names_filled.csv # Local symbol/name map when installed
    |-- docs/
    |   |-- requirements.txt
    |   |-- STRATEGY_LANGUAGE.md
    |   |-- CHANGELOG_DEV.md
    |   |-- architecture/
    |   |-- patches/
    |   `-- strategy_examples/
    |-- scripts/                 # Local maintenance and diagnostic scripts
    `-- utils/                   # Shared chart and utility helpers
```

## Installation

### 1. Clone and create a virtual environment

```powershell
git clone https://github.com/09hz/AlgoTrader.git
cd AlgoTrader
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Command Prompt activation:

```bat
.venv\Scripts\activate.bat
```

macOS/Linux activation:

```bash
source .venv/bin/activate
```

### 2. Install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r Live\docs\requirements.txt
```

macOS/Linux:

```bash
python -m pip install --upgrade pip
python -m pip install -r Live/docs/requirements.txt
```

Optional packages:

```powershell
# PostgreSQL backend
python -m pip install "psycopg[binary]"

# Faster parquet replay caches
python -m pip install pyarrow fastparquet
```

### 3. Symbol files

The application expects these local files under `Live/data/`:

- `nasdaq_tickers_simple.txt`
- `nasdaq_symbol_names_filled.csv`

These files may exist in a development workspace, but `Live/data/` is intentionally gitignored and a clean clone will not contain them. Build them from the official [Nasdaq Trader symbol directory](https://www.nasdaqtrader.com/trader.aspx?id=symboldirdefs) and [Nasdaq Screener](https://www.nasdaq.com/market-activity/stocks/screener), then place them in `Live/data/` with the exact names above.

Expected formats:

```text
# nasdaq_tickers_simple.txt: one symbol per line, no header
AAPL
MSFT

# nasdaq_symbol_names_filled.csv: CSV header followed by symbol/name rows
symbol,name
AAPL,Apple Inc.
MSFT,Microsoft Corporation
```

### 4. Interactive Brokers

For IBKR-backed live or historical data:

1. Install and open Trader Workstation or IB Gateway.
2. Enable socket API clients in the API settings.
3. Confirm the configured host, port, and client ID.
4. Paper TWS commonly uses port `7497`; live TWS commonly uses `7496`.
5. Confirm the account has the required exchange market-data permissions.

IBKR references:

- [API market-data subscriptions](https://www.interactivebrokers.com/campus/ibkr-api-page/market-data-subscriptions/)
- [Market-data pricing](https://www.interactivebrokers.com/en/pricing/market-data-pricing.php)
- [Account requirements](https://www.interactivebrokers.com/en/accounts/required-minimums.php)

### 5. Database configuration

SQLite is the default and requires no database server. Its default path is `Live/data/catalog/data_catalog.sqlite`.

For PostgreSQL, install `psycopg`, create the database/user, and set the variables shown in `.env.example`:

```env
ALGOTRADER_DB_BACKEND=postgres
ALGOTRADER_DB_HOST=localhost
ALGOTRADER_DB_PORT=5432
ALGOTRADER_DB_NAME=algotrader
ALGOTRADER_DB_USER=algotrader_app
ALGOTRADER_DB_SCHEMA=algotrader
ALGOTRADER_DB_PASSWORD=your-local-password
```

PowerShell helpers are available in `scripts/setup_postgres.ps1`, `scripts/set_postgres_env.ps1`, and `scripts/check_postgres.ps1`.

Do not commit database passwords, broker credentials, API keys, `.env`, or `.env.local` files.

## Running the Application

From the repository root:

```powershell
python Live\app.py
```

macOS/Linux:

```bash
python Live/app.py
```

Open `http://127.0.0.1:8050/` in a browser.

The app is designed to start from one command. Users should not need to run layout-validation commands or launch separate terminals for Auto Lab, Data Library, or Quant Dashboard.

## Common Workflows

### Replay and strategy testing

1. Open **Watch** and select a symbol, timeframe, and date or range.
2. Load the replay and wait for the background progress indicator to complete.
3. Use playback controls or seek to a specific bar.
4. Open **Strategy Lab**, enter a strategy, and run the overlay or backtest.
5. Review the Paper Trading and Trade Analytics sections.

### Auto Lab research

1. Open **AI Auto Lab** and enter seed symbols or use Symbol Explorer.
2. Configure the Universe period, capital assumptions, and run limits.
3. Run Universe Auto Lab and review ranked strategy candidates.
4. Configure train, unseen-test, rolling-window, cost-stress, and final-holdout settings.
5. Run Walk-Forward; it uses the exact candidate packet from the associated Universe run.
6. Review promoted candidates manually before activating a Paper Review simulation.

### Data and experiment review

1. Open **Data Library** to scan, search, preview, or ingest generated artifacts.
2. Open **Quant Dashboard** to inspect normalized experiments, strategies, backtests, universes, walk-forward results, and quality records.
3. Use **Settings** to confirm the selected SQLite/PostgreSQL backend and provider status.

## Verification and Development

Compile the main application:

```powershell
python -m py_compile Live\app.py Live\callbacks.py
```

macOS/Linux:

```bash
python -m py_compile Live/app.py Live/callbacks.py
```

Run focused Auto Lab checks:

```powershell
python Live\services\ai\auto_lab_orchestrator\symbol_discovery_self_test.py
python Live\services\ai\auto_lab_orchestrator\walk_forward_self_test.py --contract-only
python Live\services\ai\auto_lab_orchestrator\auto_lab_main_ui_self_test.py
```

macOS/Linux:

```bash
python Live/services/ai/auto_lab_orchestrator/symbol_discovery_self_test.py
python Live/services/ai/auto_lab_orchestrator/walk_forward_self_test.py --contract-only
python Live/services/ai/auto_lab_orchestrator/auto_lab_main_ui_self_test.py
```

Additional module-specific `*_self_test.py` scripts are colocated with Research Loop, Data Library, Quant Dashboard, quantitative schema, and Auto Lab modules.

## Generated and Local Files

The `.gitignore` excludes local secrets and generated state, including:

- `.env`, `.env.local`, and local provider credentials
- `.idea/`, virtual environments, and Python caches
- replay/paper caches and generated `Live/data/` research runs
- exports, reports, strategy context, and research briefs
- local SQLite databases and PostgreSQL credentials

Do not delete generated data while a replay or Auto Lab background job is running.

## Current Limitations

- Market-data availability depends on IBKR permissions, session state, and provider limits.
- Replay completeness depends on the available historical bars and cache quality.
- Dense Plotly charts and complex overlays can still be browser-intensive.
- Symbol Explorer uses a finite local peer/theme catalog and eventually cycles when candidates are exhausted.
- Auto Lab runtime grows with symbols, date range, candidates, rolling windows, and stress configurations.
- Auto Lab and Research Loop are simulation-only; promoted candidates require manual Paper Review.
- SQLite is intended for local use. PostgreSQL is recommended for larger persistent experiment collections.
- The platform primarily targets equities.

## Safety and Disclaimer

This project is for education, research, backtesting, and paper-trading simulation. It is not financial, investment, or trading advice. Historical or simulated performance does not guarantee future results.

Do not connect research-generated signals to real-money execution without an independent audit of broker integration, position sizing, risk controls, failure recovery, monitoring, security, and regulatory requirements.

Interactive Brokers, IBKR, TWS, and IB Gateway are trademarks or services of Interactive Brokers Group and/or its affiliates. This project is not affiliated with or endorsed by Interactive Brokers.
