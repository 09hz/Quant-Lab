from __future__ import annotations

# Load local .env values before app services read configuration.
try:
    from services.config.env_loader import load_app_env

    load_app_env(override=True, verbose=True)
except Exception as _env_load_exc:
    print(f"[ENV] local .env load skipped: {_env_load_exc}")


import sys
import asyncio
from datetime import date

from dash import Dash, dcc, html

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from callbacks import register_callbacks
from config import (
    APP_TITLE,
    DEFAULT_REPLAY_INDEX,
    DEFAULT_REPLAY_SPEED,
    DEFAULT_SYMBOL,
    DEFAULT_TIMEFRAME,
    UI_INTERVAL_MS,
)
from core.RealTime import RealTimeIB, TIMEFRAME_MAP
from services.market_data.provider_factory import (
    build_market_data_provider,
    get_market_data_provider_name,
)
from core.ReplayModule import ReplayEngine
from services.replay_service import ReplayService
from services.paper_cache import PaperStateCache

try:
    from services.ai.strategy_context_callbacks import register_strategy_ai_context_callbacks
except Exception:
    register_strategy_ai_context_callbacks = None
from ui.tabs_ui import (
    build_dashboard_tab,
    build_watch_tab,
    build_quotes_tab,
    build_charts_tab,
)


try:
    from services.paper_trading_service import PaperTradingService
    from core.PaperBroker import PaperBroker
    from core.RiskGuard import RiskGuard
except Exception:
    PaperTradingService = None
    PaperBroker = None
    RiskGuard = None


market_data_provider_name = get_market_data_provider_name(default="ibkr")

# RealTimeIB is still constructed for IBKR mode and for local symbol/company
# metadata compatibility. In CSV/local mode, the IBKR network connection is
# not started, so replay development can run without TWS/Gateway.
rt = RealTimeIB(host="127.0.0.1", port=4001)

if market_data_provider_name == "ibkr":
    rt.start(DEFAULT_SYMBOL, DEFAULT_TIMEFRAME)
else:
    print(
        f"[MARKET DATA] provider={market_data_provider_name}; "
        "IBKR autostart skipped.",
        flush=True,
    )

market_data_provider = build_market_data_provider(rt=rt)

replay_engine = ReplayEngine()
replay_service = ReplayService(market_data_provider, replay_engine)

paper_trading_service = None
paper_state_cache = PaperStateCache(cache_dir="cache/paper")

if PaperTradingService and PaperBroker and RiskGuard:
    paper_trading_service = PaperTradingService(
        broker=PaperBroker(
            starting_cash=100_000,
            commission_per_order=0.0,
            slippage_bps=1.0,
        ),
        risk_guard=RiskGuard(
            allowed_symbols=None,
            max_quantity=1_000,
            max_notional=25_000,
            allow_short=False,
            live_trading_enabled=False,
        ),
    )

SYMBOL_OPTIONS = market_data_provider.get_symbol_options() or rt.get_symbol_options()

app = Dash(__name__, suppress_callback_exceptions=True)
app.title = APP_TITLE

app.layout = html.Div(
    className="app-shell",
    children=[
        html.Div(
            className="topbar",
            children=[
                html.Div(id="pair-title", className="pair-title"),
                html.Div(id="quote-strip", className="quote-strip"),
            ],
        ),
        dcc.Tabs(
            id="main-tabs",
            value="dashboard",
            className="main-tabs",
            children=[
                dcc.Tab(
                    label="Dashboard",
                    value="dashboard",
                    className="main-tab",
                    selected_className="main-tab-selected",
                    children=[
                        build_dashboard_tab(
                            symbol_options=SYMBOL_OPTIONS,
                            timeframe_map=TIMEFRAME_MAP,
                            default_symbol=DEFAULT_SYMBOL,
                            default_timeframe=DEFAULT_TIMEFRAME,
                        )
                    ],
                ),
                dcc.Tab(
                    label="Watch",
                    value="watch",
                    className="main-tab",
                    selected_className="main-tab-selected",
                    children=[
                        build_watch_tab(
                            symbol_options=SYMBOL_OPTIONS,
                            default_symbol=DEFAULT_SYMBOL,
                            default_speed=DEFAULT_REPLAY_SPEED,
                            default_index=DEFAULT_REPLAY_INDEX,
                            default_date=date.today().isoformat(),
                        )
                    ],
                ),
                dcc.Tab(
                    label="Newsroom",
                    value="quotes",
                    className="main-tab",
                    selected_className="main-tab-selected",
                    children=[
                        build_quotes_tab(
                            symbol_options=SYMBOL_OPTIONS,
                            default_symbol=DEFAULT_SYMBOL,
                        )
                    ],
                ),
                dcc.Tab(
                    label="Settings",
                    value="charts",
                    className="main-tab",
                    selected_className="main-tab-selected",
                    children=[
                        build_charts_tab(
                            symbol_options=SYMBOL_OPTIONS,
                            timeframe_map=TIMEFRAME_MAP,
                            default_symbol=DEFAULT_SYMBOL,
                            default_timeframe=DEFAULT_TIMEFRAME,
                        )
                    ],
                ),
            ],
        ),

        # General UI/live refresh.
        dcc.Interval(id="ui-interval", interval=UI_INTERVAL_MS, n_intervals=0),

        # Dedicated replay heartbeat. This drives Play/Pause independently
        # from the general UI interval.
        dcc.Interval(id="replay-clock", interval=250, n_intervals=0),

        # Replay render trigger. Buttons/clock bump this store so the Watch chart
        # redraws without the slider callback fighting the clock.
        dcc.Store(id="replay-render-trigger", data=0),

        dcc.Store(
            id="watch-load-request",
            data={
                "nonce": 0,
                "symbol": DEFAULT_SYMBOL,
                "replay_date": None,
                "timeframe": "1 min",
            },
        ),

        dcc.Store(id="replay-range-job-store", data=None),

        dcc.Store(
            id="dashboard-chart-state",
            data={
                "mode": "live",
                "range_key": "1D",
                "x_range": None,
                "y_range": None,
            },
        ),
        dcc.Store(
            id="watch-chart-state",
            data={
                "mode": "live",
                "range_key": "1D",
                "x_range": None,
                "y_range": None,
            },
        ),

        dcc.Store(id="paper-trade-trigger", data=0),
        dcc.Store(
            id="strategy-script-store",
            data={
                "script": "",
                "enabled": False,
                "nonce": 0,
            },
        ),
        dcc.Store(id="zoom-state", data={}),
        dcc.Store(id="active-symbol", data=DEFAULT_SYMBOL),
        dcc.Store(id="load-status", data="Ready"),
        dcc.Store(
            id="dashboard-state",
            data={
                "symbol": DEFAULT_SYMBOL,
                "timeframe": DEFAULT_TIMEFRAME,
            },
        ),
        dcc.Store(
            id="watch-state",
            data={
                "symbol": DEFAULT_SYMBOL,
                "replay_speed": DEFAULT_REPLAY_SPEED,
                "replay_index": DEFAULT_REPLAY_INDEX,
                "replay_date": None,
            },
        ),
    ],
)

register_callbacks(
    app,
    rt,
    replay_service,
    SYMBOL_OPTIONS,
    TIMEFRAME_MAP,
    paper_trading_service=paper_trading_service,
    paper_state_cache=paper_state_cache,
    market_data_provider=market_data_provider,
)

# =============================================================================
# AI Advisor callback registration
# =============================================================================
try:
    from services.ai.advisor_callbacks import register_ai_advisor_callbacks

    register_ai_advisor_callbacks(app)
except Exception as exc:
    print(f"[AI ADVISOR] callback registration skipped: {exc}")

try:
    from services.ai.strategy_context_callbacks import register_strategy_ai_context_callbacks

    register_strategy_ai_context_callbacks(app)
except Exception as exc:
    print(f"[STRATEGY AI CONTEXT] callback registration skipped: {exc}")
# =============================================================================
# End AI Advisor callback registration
# =============================================================================


# =============================================================================
# Newsroom callback registration
# =============================================================================
try:
    from services.research.newsroom_callbacks import register_newsroom_callbacks

    register_newsroom_callbacks(app)
except Exception as exc:
    print(f"[NEWSROOM] callback registration skipped: {exc}")
# =============================================================================
# End Newsroom callback registration
# =============================================================================

# =============================================================================
# Watch live-day guard callback registration
# =============================================================================
try:
    from services.watch.live_guard_callbacks import register_watch_live_guard_callbacks

    register_watch_live_guard_callbacks(app)
except Exception as exc:
    print(f"[WATCH LIVE GUARD] callback registration skipped: {exc}")
# =============================================================================
# End Watch live-day guard callback registration
# =============================================================================


# =============================================================================
# Watch live/replay mode guard callback registration
# =============================================================================
try:
    from services.watch.live_replay_guard_callbacks import (
        register_live_replay_guard_callbacks,
    )

    register_live_replay_guard_callbacks(app)
except Exception as exc:
    print(f"[WATCH LIVE/REPLAY GUARD] callback registration skipped: {exc}")
# =============================================================================
# End Watch live/replay mode guard callback registration
# =============================================================================
# Patch 36c: Newsroom Research Analyst callbacks.
try:
    from services.ai.research_analyst_callbacks import register_research_analyst_callbacks

    register_research_analyst_callbacks(app)
except Exception as research_analyst_callbacks_exc:
    print(
        f"[RESEARCH ANALYST CALLBACKS WARNING] {research_analyst_callbacks_exc}",
        flush=True,
    )



# =============================================================================
# Research Autolab callback registration
# =============================================================================
try:
    from services.ai.research_autolab.ui_callbacks import register_research_autolab_callbacks

    register_research_autolab_callbacks(app)
except Exception as exc:
    print(f"[RESEARCH AUTOLAB] callback registration skipped: {exc}", flush=True)
# =============================================================================
# End Research Autolab callback registration
# =============================================================================

if __name__ == "__main__":
    app.run(debug=False)
