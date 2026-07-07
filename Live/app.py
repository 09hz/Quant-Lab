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
from ui.auto_lab_ui import build_auto_lab_tab

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
                    label="AI Auto Lab",
                    value="auto-lab",
                    className="main-tab",
                    selected_className="main-tab-selected",
                    children=[
                        build_auto_lab_tab(),
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

# =============================================================================
# AI Auto Lab callback registration
# =============================================================================
try:
    from services.ai.auto_lab_orchestrator.auto_lab_main_callbacks import (
        register_auto_lab_main_callbacks,
    )

    register_auto_lab_main_callbacks(app)
except Exception as exc:
    print(f"[WARN] AI Auto Lab callbacks not registered: {exc}", flush=True)
# =============================================================================
# End AI Auto Lab callback registration
# =============================================================================

# =============================================================================
# Structured official evidence preview callback registration
# =============================================================================
# Structured Evidence Reviewer callbacks kept for developer diagnostics only.
# Normal SEC workflow now uses Newsroom source checkboxes and Research Brief cards.
# =============================================================================
# End structured official evidence preview callback registration
# =============================================================================

# --- v23.4.1 Data Library Runtime Wiring Fix ---
try:
    from dash import dcc as _v23_4_1_dcc, html as _v23_4_1_html
    from ui.data_library_ui import build_data_library_layout as _v23_4_1_build_data_library_layout
    from services.data_catalog.data_library_callbacks import register_data_library_callbacks as _v23_4_1_register_data_library_callbacks

    def _v23_4_1_has_data_library(component):
        stack = [component]
        while stack:
            item = stack.pop()
            if item is None:
                continue
            if isinstance(item, (list, tuple)):
                stack.extend(item)
                continue
            if getattr(item, "id", None) == "data-library-root":
                return True
            children = getattr(item, "children", None)
            if isinstance(children, (list, tuple)):
                stack.extend(children)
            elif children is not None:
                stack.append(children)
        return False

    def _v23_4_1_is_tabs(component):
        name = component.__class__.__name__.lower()
        return name == "tabs" or name.endswith(".tabs") or "tabs" in name

    def _v23_4_1_make_data_library_tab():
        try:
            return _v23_4_1_dcc.Tab(
                label="Data Library",
                value="data-library",
                children=[_v23_4_1_build_data_library_layout()],
            )
        except Exception:
            return _v23_4_1_html.Div(
                id="data-library-tab-fallback",
                children=[_v23_4_1_build_data_library_layout()],
            )

    def _v23_4_1_attach_to_tabs(component):
        attached = {"done": False}

        def _walk(value):
            if value is None or attached["done"]:
                return value

            if isinstance(value, list):
                return [_walk(item) for item in value]
            if isinstance(value, tuple):
                return tuple(_walk(item) for item in value)

            if _v23_4_1_has_data_library(value):
                attached["done"] = True
                return value

            if _v23_4_1_is_tabs(value):
                children = getattr(value, "children", None)
                tab = _v23_4_1_make_data_library_tab()
                try:
                    if children is None:
                        value.children = [tab]
                    elif isinstance(children, (list, tuple)):
                        value.children = [*list(children), tab]
                    else:
                        value.children = [children, tab]
                    attached["done"] = True
                    return value
                except Exception:
                    pass

            children = getattr(value, "children", None)
            if isinstance(children, (list, tuple)):
                try:
                    value.children = [_walk(item) for item in children]
                except Exception:
                    pass
            elif children is not None and not isinstance(children, str):
                try:
                    value.children = _walk(children)
                except Exception:
                    pass

            return value

        return _walk(component), attached["done"]

    def _v23_4_1_attach_data_library(layout):
        if layout is None:
            return _v23_4_1_build_data_library_layout()

        if _v23_4_1_has_data_library(layout):
            return layout

        try:
            layout, attached_to_tabs = _v23_4_1_attach_to_tabs(layout)
            if attached_to_tabs or _v23_4_1_has_data_library(layout):
                return layout
        except Exception:
            pass

        panel = _v23_4_1_html.Div(
            id="data-library-runtime-fallback-section",
            children=[
                _v23_4_1_html.Hr(),
                _v23_4_1_html.H2("Data Library"),
                _v23_4_1_build_data_library_layout(),
            ],
        )
        try:
            children = getattr(layout, "children", None)
            if children is None:
                layout.children = [panel]
            elif isinstance(children, (list, tuple)):
                layout.children = [*list(children), panel]
            else:
                layout.children = [children, panel]
            return layout
        except Exception:
            return _v23_4_1_html.Div([layout, panel])

    def _v23_4_1_wrap_layout_callable(fn):
        if getattr(fn, "_v23_4_1_data_library_wrapped", False):
            return fn

        def _wrapped(*args, **kwargs):
            return _v23_4_1_attach_data_library(fn(*args, **kwargs))

        _wrapped.__name__ = getattr(fn, "__name__", "wrapped_data_library_layout_v23_4_1")
        _wrapped.__doc__ = getattr(fn, "__doc__", None)
        _wrapped._v23_4_1_data_library_wrapped = True
        return _wrapped

    if "app" in globals():
        if callable(getattr(app, "layout", None)):
            app.layout = _v23_4_1_wrap_layout_callable(app.layout)
        elif getattr(app, "layout", None) is not None:
            app.layout = _v23_4_1_attach_data_library(app.layout)
        else:
            app.layout = _v23_4_1_build_data_library_layout()

        try:
            if getattr(app, "validation_layout", None) is not None:
                app.validation_layout = _v23_4_1_attach_data_library(app.validation_layout)
        except Exception:
            pass

        _v23_4_1_register_data_library_callbacks(app)
        print("v23.4.1 Data Library runtime wiring loaded.")

except Exception as _v23_4_1_data_library_error:
    print(f"v23.4.1 Data Library Runtime Wiring Fix failed: {_v23_4_1_data_library_error}")
# --- end v23.4.1 Data Library Runtime Wiring Fix ---

if __name__ == "__main__":
    app.run(debug=False)

# --- v23.4 Data Library UI Integration ---
try:
    from dash import dcc as _v23_4_dcc, html as _v23_4_html
    from ui.data_library_ui import build_data_library_layout as _v23_4_build_data_library_layout
    from services.data_catalog.data_library_callbacks import register_data_library_callbacks as _v23_4_register_data_library_callbacks

    def _v23_4_component_has_data_library(component):
        stack = [component]
        while stack:
            item = stack.pop()
            if item is None:
                continue
            if isinstance(item, (list, tuple)):
                stack.extend(item)
                continue
            if getattr(item, "id", None) == "data-library-root":
                return True
            children = getattr(item, "children", None)
            if isinstance(children, (list, tuple)):
                stack.extend(children)
            elif children is not None:
                stack.append(children)
        return False

    def _v23_4_attach_to_first_tabs(component):
        attached = {"done": False}

        def _walk(value):
            if value is None or attached["done"]:
                return value
            if isinstance(value, list):
                return [_walk(item) for item in value]
            if isinstance(value, tuple):
                return tuple(_walk(item) for item in value)

            if value.__class__.__name__ == "Tabs" and not _v23_4_component_has_data_library(value):
                tab = _v23_4_dcc.Tab(
                    label="Data Library",
                    value="data-library",
                    children=[_v23_4_build_data_library_layout()],
                )
                children = getattr(value, "children", None)
                if children is None:
                    value.children = [tab]
                elif isinstance(children, (list, tuple)):
                    value.children = [*list(children), tab]
                else:
                    value.children = [children, tab]
                attached["done"] = True
                return value

            children = getattr(value, "children", None)
            if isinstance(children, (list, tuple)):
                try:
                    value.children = [_walk(item) for item in children]
                except Exception:
                    pass
            elif children is not None and not isinstance(children, str):
                try:
                    value.children = _walk(children)
                except Exception:
                    pass
            return value

        return _walk(component), attached["done"]

    def _v23_4_attach_data_library(layout):
        if _v23_4_component_has_data_library(layout):
            return layout

        try:
            layout, attached_to_tabs = _v23_4_attach_to_first_tabs(layout)
            if attached_to_tabs or _v23_4_component_has_data_library(layout):
                return layout
        except Exception:
            pass

        panel = _v23_4_build_data_library_layout()
        try:
            children = getattr(layout, "children", None)
            if children is None:
                layout.children = [panel]
            elif isinstance(children, (list, tuple)):
                layout.children = [*list(children), panel]
            else:
                layout.children = [children, panel]
            return layout
        except Exception:
            return _v23_4_html.Div([layout, panel])

    def _v23_4_wrap_layout_callable(fn):
        if getattr(fn, "_v23_4_data_library_wrapped", False):
            return fn

        def _wrapped(*args, **kwargs):
            return _v23_4_attach_data_library(fn(*args, **kwargs))

        _wrapped.__name__ = getattr(fn, "__name__", "wrapped_data_library_layout")
        _wrapped.__doc__ = getattr(fn, "__doc__", None)
        _wrapped._v23_4_data_library_wrapped = True
        return _wrapped

    if "app" in globals():
        if callable(getattr(app, "layout", None)):
            app.layout = _v23_4_wrap_layout_callable(app.layout)
        elif getattr(app, "layout", None) is not None:
            app.layout = _v23_4_attach_data_library(app.layout)

        _v23_4_register_data_library_callbacks(app)

except Exception as _v23_4_data_library_error:
    print(f"v23.4 Data Library UI Integration failed: {_v23_4_data_library_error}")
# --- end v23.4 Data Library UI Integration ---
