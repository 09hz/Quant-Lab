# Quant Lab – Comprehensive Feature Guide

This document describes all major features of the application, how they work, and which files control and manipulate them. It is based solely on tracked repository files (git ls-files), excluding anything in .gitignore.

## Top-Level Application Flow

- Entry point: Live/app.py – Initializes env, providers, replay, services, and Dash tabs, then registers callbacks.
- Core UI callbacks: Live/callbacks.py – Orchestrates data loads, replay control, chart renders, overlays, and strategy/backtest actions.
- Configuration: Live/config.py – App title, defaults (symbol, timeframe, replay speed/index), and UI timer.

## Main Features (Overview)

1) Dashboard – Live/cached chart, symbol/timeframe controls, metrics strip, quick ranges.
2) Watch – Replay engine with play/pause/seek/speed, strategy overlays, stats.
3) Strategy Lab & Backtesting – Local strategy language, overlays, backtests, analytics.
4) Paper Trading (Simulation) – Local simulated broker with risk guard; no live orders.
5) AI Auto Lab – Symbol explorer, universe testing, mutations, ranking, walk-forward.
6) Newsroom & Research – Trusted-source evidence (SEC/FRED/BLS), structured briefs.
7) Data Library – Artifact catalog, search, previews, ingestion, database health.
8) Quant Dashboard – Read-only views of experiments, strategies, universes, walks, quality.
9) Settings – Provider/runtime diagnostics and configuration status.

## Feature Details and Controlling Files

### Dashboard
- Purpose: At-a-glance market view: symbol/timeframe selectors, metrics, chart, stats tiles, range buttons.
- Primary UI: Live/ui/tabs_ui.py (build_dashboard_tab)
- Renderers: Live/renderers/watch_chart_renderer.py (base visuals)
- Callbacks: Live/callbacks.py (metrics, chart data, stats grid)
- Market data: Live/services/market_data/* via provider_factory
- Config: Live/config.py

### Watch (Replay Workspace)
- Purpose: Single-day and range replay with controls, seek, speed; chart viewport + stats.
- Primary UI: Live/ui/tabs_ui.py (build_watch_tab)
- Core engines: Live/core/ReplayModule.py (ReplayEngine)
- Services: Live/services/replay_service.py, Live/services/replay/* (range jobs, safety, routing)
- Market data: Live/services/market_data/* (CSV/IBKR)
- Renderers: Live/renderers/watch_chart_renderer.py; overlays via strategy overlay renderer
- Callbacks: Live/callbacks.py

### Strategy Lab & Backtesting
- Purpose: Author strategy scripts (Pine-like), run overlays and backtests; plots and trade markers.
- Strategy engine: Live/core/StrategyEngine.py; functions registry in Live/core/StrategyFunctionRegistry.py
- Indicators: Live/core/IndicatorEngine.py
- Backtests: Live/core/BackTestEngine.py
- UI: Live/ui/tabs_ui.py (strategy editor panel, actions, status)
- Overlay service: Live/services/strategy_overlay_service.py
- Renderers: Live/renderers/strategy_overlay_renderer.py
- Callbacks: Live/callbacks.py
- Docs: Live/docs/STRATEGY_LANGUAGE.md and Live/docs/strategy_examples/

### Paper Trading (Simulation Only)
- Purpose: Visual strategy simulation with local broker and explicit risk guard; no real orders.
- Broker: Live/core/PaperBroker.py
- Risk: Live/core/RiskGuard.py (TradeIntent, bounds)
- Service: Live/services/paper_trading_service.py; cache Live/services/paper_cache.py
- UI: Integrated in Watch/Strategy areas (callbacks, overlays)
- Safety: Live/services/safety/*

### AI Auto Lab
- Purpose: Automated, simulation-only research workflow: symbol discovery, universe runs, mutations, ranking, walk-forward, reports, promotion to manual Paper Review.
- UI: Live/ui/auto_lab_ui.py
- Orchestrator: Live/services/ai/auto_lab_orchestrator/
  - symbol_discovery.py, universe_runner.py, mutator.py, scorecard.py, walk_forward_runner.py, orchestrator.py, *_self_test.py
- Services: Live/services/ai/* (advisor, callbacks, context), Live/services/research_loop/* (candidate pipeline)
- Persistence/Reports: Live/services/quant_schema/*, Live/services/quant_dashboard/*, Live/services/artifacts/*
- Callbacks: Live/services/ai/auto_lab_orchestrator/auto_lab_main_callbacks.py and Live/callbacks.py glue

### Newsroom & Research
- Purpose: Trusted-source evidence gathering with quality checks and structured briefs.
- UI: Live/ui/newsroom_ui.py, Live/ui/structured_evidence_preview_ui.py
- Sources/Adapters: Live/services/research/* (SEC, FRED, BLS, coverage, hygiene)
- Artifacts: Live/services/artifacts/*; writer docs in docs/artifact_writer.md
- Docs/Design: docs/output_router.md, docs/direct_producer_wiring.md

### Data Library
- Purpose: Catalog generated artifacts, search and preview; ingestion into DB; health.
- UI: Live/ui/data_library_ui.py
- Catalog: Live/services/data_catalog/*
- Database: Live/services/database/*
- Quant schema: Live/services/quant_schema/*

### Quant Dashboard
- Purpose: Read-only normalized views of experiments, strategies, backtests, universes, walk-forward runs, and data-quality events. Launch Research Loop.
- UI/Callbacks/Queries: Live/services/quant_dashboard/*
- Schema/Repos: Live/services/quant_schema/*

### Settings
- Purpose: Provider/runtime configuration visibility and diagnostics.
- UI: Live/ui/settings_ui.py
- Providers: Live/services/market_data/*; factory Live/services/market_data/provider_factory.py
- Config loading: Live/services/config/env_loader.py (loaded by Live/app.py)

### Market Data Providers
- Purpose: Provide live/historical bars and symbol options via CSV or IBKR.
- Factory: Live/services/market_data/provider_factory.py
- IBKR: Live/core/RealTime.py, Live/services/market_data/ibkr_provider.py
- CSV: Live/services/market_data/csv_provider.py (root from env CSV_MARKET_DATA_ROOT)
- Timeframe map: Live/core/RealTime.py (TIMEFRAME_MAP)

### Charting and Rendering
- Shared chart utils: Live/utils/chart_utils.py
- Watch chart visuals: Live/renderers/watch_chart_renderer.py
- Strategy overlay visuals: Live/renderers/strategy_overlay_renderer.py
- Viewport/Bar view services: Live/services/chart_viewport_service.py, Live/services/bar_view_service.py

### Models and UI Composition
- Models: Live/models/* (UI/domain models)
- Tabs composition: Live/ui/tabs_ui.py (Dashboard/Watch/Newsroom/Auto Lab/Settings)
- Additional UIs: Live/ui/research_autolab_ui.py, Live/ui/auto_lab_memory_packet_ui.py

## Data and Persistence
- SQLite default path: Live/data/catalog/data_catalog.sqlite (gitignored)
- Optional PostgreSQL: configure via .env.example; helpers in scripts/
- Migrations and repos: Live/services/database/*, Live/services/quant_schema/*

## Safety and Boundaries
- Research/Execution safety: Live/services/safety/*
- App disclaimer: README.md; no live broker orders from research flows

## Developer Utilities
- Self tests: Live/services/**/**/*_self_test.py
- Scripts: scripts/ (Postgres setup and checks)
- Docs: docs/ and Live/docs/

## Appendix: Full Tracked File Tree

The following tree is generated from git ls-files (respects .gitignore):

<!-- FILE TREE WILL BE APPENDED BELOW BY SCRIPT -->
