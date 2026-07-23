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

# BEGIN v24.5 quant output wiring
try:
    from services.quant_schema.runtime_wiring import install_quant_output_hooks
    install_quant_output_hooks()
except Exception as _v24_5_quant_wiring_exc:
    print(f"[v24.5 quant wiring] disabled: {type(_v24_5_quant_wiring_exc).__name__}: {_v24_5_quant_wiring_exc}")
# END v24.5 quant output wiring


# BEGIN v24.8.3 native quant dashboard tab
# Rebuilt from docs/quant_dashboard_audit.md (portable spec)
try:
    import os as _v24_8_3_os
    from pathlib import Path as _v24_8_3_Path

    from dash import Input as _v24_8_3_Input
    from dash import Output as _v24_8_3_Output
    from dash import dcc as _v24_8_3_dcc
    from dash import html as _v24_8_3_html

    from services.quant_dashboard.queries import load_quant_dashboard as _v24_8_3_load_quant_dashboard

    def _v24_8_3_find_repo_root():
        here = _v24_8_3_Path(__file__).resolve()
        for parent in [here, *here.parents]:
            if (parent / "Live" / "app.py").exists():
                return parent
            if parent.name.lower() == "live" and (parent / "app.py").exists():
                return parent.parent
        return here.parent.parent

    def _v24_8_3_children_list(component):
        children = getattr(component, "children", None)
        if children is None:
            return []
        if isinstance(children, list):
            return children
        if isinstance(children, tuple):
            return list(children)
        return [children]

    def _v24_8_3_find_component_by_id(component, target_id):
        if getattr(component, "id", None) == target_id:
            return component
        for child in _v24_8_3_children_list(component):
            found = _v24_8_3_find_component_by_id(child, target_id)
            if found is not None:
                return found
        return None

    def _v24_8_3_tab_label(tab):
        try:
            return str(getattr(tab, "label", ""))
        except Exception:
            return ""

    def _v24_8_3_tab_value(tab):
        try:
            return str(getattr(tab, "value", ""))
        except Exception:
            return ""

    def _v24_8_3_is_settings_tab(tab):
        label = _v24_8_3_tab_label(tab).strip().lower()
        value = _v24_8_3_tab_value(tab).strip().lower()
        return label == "settings" or value in {"settings", "charts"}

    def _v24_8_3_is_quant_dashboard_tab(tab):
        label = _v24_8_3_tab_label(tab).strip().lower()
        value = _v24_8_3_tab_value(tab).strip().lower()
        return label == "quant dashboard" or value == "quant-dashboard"

    def _v24_8_3_fmt(value):
        if value is None:
            return ""
        if isinstance(value, float):
            return f"{value:.4f}"
        text = str(value)
        return text if len(text) <= 140 else text[:137] + "..."

    def _v24_8_3_payload_dict(payload):
        if hasattr(payload, "to_dict"):
            return payload.to_dict()
        if isinstance(payload, dict):
            return payload
        return {
            "status": "FAIL",
            "backend": "",
            "repo_root": "",
            "counts": {},
            "sections": {},
            "errors": [f"Unsupported payload type: {type(payload).__name__}"],
            "message": "Quant Dashboard payload could not be rendered.",
        }

    def _v24_8_3_status_view(payload_data):
        status = str(payload_data.get("status", "UNKNOWN"))
        class_name = (
            "quant-native-status-pass" if status == "PASS"
            else "quant-native-status-warn" if status == "WARN"
            else "quant-native-status-fail"
        )
        children = [
            _v24_8_3_html.Div(f"Status: {status}", className=class_name),
            _v24_8_3_html.Div(f"Backend: {payload_data.get('backend', '')}"),
            _v24_8_3_html.Div(str(payload_data.get("message", ""))),
            _v24_8_3_html.Div(f"Repo: {payload_data.get('repo_root', '')}", className="quant-native-muted"),
        ]
        errors = payload_data.get("errors") or []
        if errors:
            children.append(
                _v24_8_3_html.Details(
                    children=[
                        _v24_8_3_html.Summary("Warnings / errors"),
                        _v24_8_3_html.Pre("\n".join(str(item) for item in errors[:15])),
                    ]
                )
            )
        return _v24_8_3_html.Div(children=children, className="quant-native-card")

    def _v24_8_3_counts_view(counts):
        counts = counts or {}
        if not counts:
            return _v24_8_3_html.Div("No quant table counts available yet.", className="quant-native-muted")
        tiles = []
        for table, value in counts.items():
            tiles.append(
                _v24_8_3_html.Div(
                    className="quant-native-count-tile",
                    children=[
                        _v24_8_3_html.Div(str(table).replace("_", " ").title(), className="quant-native-count-label"),
                        _v24_8_3_html.Div(str(value), className="quant-native-count-value"),
                    ],
                )
            )
        return _v24_8_3_html.Div(className="quant-native-count-grid", children=tiles)

    def _v24_8_3_section_table(section_key, rows):
        titles = {
            "recent_experiments": "Recent Experiments",
            "recent_strategies": "Recent Strategies",
            "best_backtests": "Best Backtests",
            "walk_forward_runs": "Walk-Forward Runs",
            "universe_runs": "Universe Runs",
            "data_quality_events": "Data Quality Events",
        }
        preferences = {
            "recent_experiments": ["created_at", "experiment_id", "module", "experiment_name", "status"],
            "recent_strategies": ["created_at", "strategy_run_id", "strategy_name", "strategy_family", "symbol", "status"],
            "best_backtests": ["created_at", "backtest_run_id", "symbol", "strategy_name", "sharpe", "total_return", "max_drawdown", "win_rate", "trade_count"],
            "walk_forward_runs": ["created_at", "walk_forward_run_id", "symbol", "strategy_name", "avg_sharpe", "pass_rate", "status"],
            "universe_runs": ["created_at", "universe_run_id", "universe_name", "theme", "selected_count", "status"],
            "data_quality_events": ["created_at", "event_id", "symbol", "severity", "event_type", "message"],
        }
        rows = rows or []
        title = titles.get(section_key, str(section_key).replace("_", " ").title())
        if not rows:
            return _v24_8_3_html.Div(
                className="quant-native-card",
                children=[
                    _v24_8_3_html.H3(title),
                    _v24_8_3_html.Div("No rows yet.", className="quant-native-muted"),
                ],
            )
        preferred = [col for col in preferences.get(section_key, []) if any(col in row for row in rows)]
        extras = []
        for row in rows:
            for col in row.keys():
                if col not in preferred and col not in extras:
                    extras.append(col)
        columns = (preferred + extras)[:10]
        return _v24_8_3_html.Div(
            className="quant-native-card quant-native-table-card",
            children=[
                _v24_8_3_html.H3(title),
                _v24_8_3_html.Table([
                    _v24_8_3_html.Thead(_v24_8_3_html.Tr([_v24_8_3_html.Th(col) for col in columns])),
                    _v24_8_3_html.Tbody([
                        _v24_8_3_html.Tr([_v24_8_3_html.Td(_v24_8_3_fmt(row.get(col))) for col in columns])
                        for row in rows
                    ]),
                ]),
            ],
        )

    def _v24_8_3_build_native_quant_dashboard_tab():
        repo_root = str(_v24_8_3_find_repo_root())
        default_backend = _v24_8_3_os.environ.get("ALGOTRADER_DB_BACKEND", "sqlite").strip().lower()
        if default_backend not in {"sqlite", "postgres"}:
            default_backend = "sqlite"
        return _v24_8_3_dcc.Tab(
            label="Quant Dashboard",
            value="quant-dashboard",
            className="main-tab",
            selected_className="main-tab-selected",
            children=[
                _v24_8_3_html.Div(
                    className="quant-native-page",
                    children=[
                        _v24_8_3_html.Div(
                            className="quant-native-header",
                            children=[
                                _v24_8_3_html.Div([
                                    _v24_8_3_html.H2("Quant Research Dashboard"),
                                    _v24_8_3_html.Div(
                                        "Native read-only dashboard. One main app, no second terminal. Research/simulation only.",
                                        className="quant-native-muted",
                                    ),
                                ]),
                                _v24_8_3_html.Div("No broker calls. No live orders.", className="quant-native-safety-pill"),
                            ],
                        ),
                        _v24_8_3_html.Div(
                            className="quant-native-card quant-native-controls",
                            children=[

                                _v24_8_3_html.Label("Rows"),
                                _v24_8_3_dcc.Dropdown(
                                    id="quant-dashboard-row-limit",
                                    options=[
                                        {"label": "5 rows", "value": 5},
                                        {"label": "10 rows", "value": 10},
                                        {"label": "25 rows", "value": 25},
                                        {"label": "50 rows", "value": 50},
                                        {"label": "100 rows", "value": 100},
                                        {"label": "150 rows", "value": 150},
                                        {"label": "200 rows", "value": 200},
                                        {"label": "Max", "value": 9999},
                                    ],
                                    value=10,
                                    clearable=False,
                                ),
                                _v24_8_3_html.Label("Backend"),
                                _v24_8_3_dcc.Dropdown(
                                    id="quant-dashboard-native-backend",
                                    value=default_backend,
                                    clearable=False,
                                    options=[
                                        {"label": "SQLite fallback", "value": "sqlite"},
                                        {"label": "PostgreSQL", "value": "postgres"},
                                    ],
                                ),


                                _v24_8_3_html.Button("Refresh", id="quant-dashboard-native-refresh", n_clicks=0),
                                _v24_8_3_dcc.Store(id="quant-dashboard-native-repo-root", data=repo_root),
                            ],
                        ),
                        _v24_8_3_html.Div(id="quant-dashboard-native-status"),
                        _v24_8_3_html.Div(id="quant-dashboard-native-counts"),
                        _v24_8_3_html.Div(id="quant-dashboard-native-sections", className="quant-native-sections"),
                    ],
                )
            ],
        )



    def _v24_8_3_install_native_quant_dashboard_tab():
        main_tabs = _v24_8_3_find_component_by_id(app.layout, "main-tabs")
        if main_tabs is None:
            print("[v24.8.3 native quant dashboard tab] main-tabs not found; skipped", flush=True)
            return
        current_tabs = _v24_8_3_children_list(main_tabs)
        filtered_tabs, settings_tabs = [], []
        for tab in current_tabs:
            if _v24_8_3_is_quant_dashboard_tab(tab):
                continue
            if _v24_8_3_is_settings_tab(tab):
                settings_tabs.append(tab); continue
            filtered_tabs.append(tab)
        filtered_tabs.append(_v24_8_3_build_native_quant_dashboard_tab())
        filtered_tabs.extend(settings_tabs)
        main_tabs.children = filtered_tabs

    def _v24_8_3_register_native_quant_dashboard_callbacks():
        if getattr(app, "_v24_8_3_native_quant_dashboard_callbacks_registered", False):
            return
        @app.callback(
            _v24_8_3_Output("quant-dashboard-native-status", "children"),
            _v24_8_3_Output("quant-dashboard-native-counts", "children"),
            _v24_8_3_Output("quant-dashboard-native-sections", "children"),
            _v24_8_3_Input("quant-dashboard-native-refresh", "n_clicks"),
            _v24_8_3_Input("quant-dashboard-native-backend", "value"),
            _v24_8_3_Input("quant-dashboard-row-limit", "value"),
            _v24_8_3_Input("quant-dashboard-native-repo-root", "data"),
            prevent_initial_call=False,
        )
        def _v24_8_3_refresh_native_quant_dashboard(_n_clicks, selected_backend, selected_limit, selected_repo_root):
            payload = _v24_8_3_load_quant_dashboard(
                repo_root=selected_repo_root or str(_v24_8_3_find_repo_root()),
                backend=selected_backend or "sqlite",
                limit=selected_limit or 10,
            )
            data = _v24_8_3_payload_dict(payload)
            sections = data.get("sections") or {}
            return (
                _v24_8_3_status_view(data),
                _v24_8_3_counts_view(data.get("counts") or {}),
                [_v24_8_3_section_table(key, rows) for key, rows in sections.items()],
            )
        app._v24_8_3_native_quant_dashboard_callbacks_registered = True

    _v24_8_3_install_native_quant_dashboard_tab()
    _v24_8_3_register_native_quant_dashboard_callbacks()

except Exception as _v24_8_3_native_quant_dashboard_exc:
    print(
        f"[v24.8.3 native quant dashboard tab] disabled: "
        f"{type(_v24_8_3_native_quant_dashboard_exc).__name__}: {_v24_8_3_native_quant_dashboard_exc}",
        flush=True,
    )
# END v24.8.3 native quant dashboard tab

# BEGIN v24.9.1 research loop controls in quant dashboard
try:
    from dash import Input as _v24_9_1_Input
    from dash import Output as _v24_9_1_Output
    from dash import State as _v24_9_1_State
    from dash import dcc as _v24_9_1_dcc
    from dash import html as _v24_9_1_html

    from services.research_loop.models import ResearchLoopConfig as _v24_9_1_ResearchLoopConfig
    from services.research_loop.orchestrator import run_research_loop as _v24_9_1_run_research_loop

    def _v24_9_1_children_list(component):
        children = getattr(component, "children", None)
        if children is None:
            return []
        if isinstance(children, list):
            return children
        if isinstance(children, tuple):
            return list(children)
        return [children]

    def _v24_9_1_find_component_by_id(component, target_id):
        if getattr(component, "id", None) == target_id:
            return component
        for child in _v24_9_1_children_list(component):
            found = _v24_9_1_find_component_by_id(child, target_id)
            if found is not None:
                return found
        return None

    def _v24_9_1_find_component_by_class(component, target_class):
        class_name = getattr(component, "className", "") or ""
        try:
            class_text = str(class_name)
        except Exception:
            class_text = ""
        if target_class in class_text.split() or target_class in class_text:
            return component
        for child in _v24_9_1_children_list(component):
            found = _v24_9_1_find_component_by_class(child, target_class)
            if found is not None:
                return found
        return None

    def _v24_9_1_parse_symbols(value):
        symbols = []
        for part in str(value or "").replace(";", ",").split(","):
            cleaned = part.strip().upper()
            if cleaned and cleaned not in symbols:
                symbols.append(cleaned)
        return symbols or ["AMD", "NVDA", "SMH"]

    def _v24_9_1_repo_root_from_store(value):
        if value:
            return str(value)
        try:
            return str(_v24_8_3_find_repo_root())  # defined by v24.8.3 native Quant tab
        except Exception:
            from pathlib import Path as _Path
            here = _Path(__file__).resolve()
            return str(here.parent.parent)

    def _v24_9_1_build_research_loop_panel():
        return _v24_9_1_html.Div(
            id="research-loop-controls-panel",
            className="quant-native-card research-loop-controls-panel",
            children=[
                _v24_9_1_html.Div(
                    className="research-loop-controls-header",
                    children=[
                        _v24_9_1_html.Div(
                            children=[
                                _v24_9_1_html.H3("Research Loop"),
                                _v24_9_1_html.Div(
                                    "Generate strategy candidates, proxy-test them, store results in Quant Schema, then auto-refresh this dashboard.",
                                    className="quant-native-muted",
                                ),
                            ]
                        ),
                        _v24_9_1_html.Div(
                            "Simulation only",
                            className="research-loop-safety-pill",
                        ),
                    ],
                ),
                _v24_9_1_html.Div(
                    className="research-loop-controls-grid",
                    children=[
                        _v24_9_1_html.Label("Theme"),
                        _v24_9_1_dcc.Input(
                            id="research-loop-theme",
                            type="text",
                            value="AI infrastructure semiconductors",
                            debounce=True,
                        ),
                        _v24_9_1_html.Label("Symbols"),
                        _v24_9_1_dcc.Input(
                            id="research-loop-symbols",
                            type="text",
                            value="AMD,NVDA,SMH",
                            debounce=True,
                        ),
                        _v24_9_1_html.Label("Candidates"),
                        _v24_9_1_dcc.Input(
                            id="research-loop-max-candidates",
                            type="number",
                            min=1,
                            max=25,
                            step=1,
                            value=10,
                            debounce=True,
                        ),
                        _v24_9_1_html.Label("Backend"),
                        _v24_9_1_dcc.Dropdown(
                            id="research-loop-backend",
                            value="sqlite",
                            clearable=False,
                            options=[
                                {"label": "SQLite fallback", "value": "sqlite"},
                                {"label": "PostgreSQL", "value": "postgres"},
                            ],
                        ),
                        _v24_9_1_html.Div(),
                        _v24_9_1_html.Button(
                            "Run Research Loop",
                            id="research-loop-run-button",
                            n_clicks=0,
                            className="research-loop-run-button",
                        ),
                    ],
                ),
                _v24_9_1_html.Div(
                    id="research-loop-run-status",
                    className="research-loop-run-status quant-native-muted",
                    children="Ready. This runs a simulation-only research loop and writes results to Quant Schema.",
                ),
                _v24_9_1_html.Div(
                    id="research-loop-last-report",
                    className="research-loop-last-report",
                ),
            ],
        )

    def _v24_9_1_install_research_loop_panel():
        if _v24_9_1_find_component_by_id(app.layout, "research-loop-controls-panel") is not None:
            return

        quant_page = _v24_9_1_find_component_by_class(app.layout, "quant-native-page")
        if quant_page is None:
            print("[v24.9.1 research loop controls] quant-native-page not found; skipped", flush=True)
            return

        children = _v24_9_1_children_list(quant_page)
        panel = _v24_9_1_build_research_loop_panel()

        # Insert after header and existing dashboard controls when possible.
        insert_at = 2 if len(children) >= 2 else len(children)
        children.insert(insert_at, panel)
        quant_page.children = children

    def _v24_9_1_register_research_loop_callbacks():
        if getattr(app, "_v24_9_1_research_loop_callbacks_registered", False):
            return

        @app.callback(
            _v24_9_1_Output("research-loop-run-status", "children"),
            _v24_9_1_Output("research-loop-last-report", "children"),
            _v24_9_1_Output("quant-dashboard-native-refresh", "n_clicks"),
            _v24_9_1_Input("research-loop-run-button", "n_clicks"),
            _v24_9_1_State("research-loop-theme", "value"),
            _v24_9_1_State("research-loop-symbols", "value"),
            _v24_9_1_State("research-loop-max-candidates", "value"),
            _v24_9_1_State("research-loop-backend", "value"),
            _v24_9_1_State("quant-dashboard-native-repo-root", "data"),
            _v24_9_1_State("quant-dashboard-native-refresh", "n_clicks"),
            prevent_initial_call=True,
        )
        def _v24_9_1_run_loop_from_browser(n_clicks, theme, symbols_text, max_candidates, backend, repo_root, current_refresh_clicks):
            if not n_clicks:
                return "Ready.", "", current_refresh_clicks or 0

            symbols = _v24_9_1_parse_symbols(symbols_text)
            backend = backend if backend in {"sqlite", "postgres"} else "sqlite"
            try:
                max_candidates = int(max_candidates or 10)
            except Exception:
                max_candidates = 10
            max_candidates = max(1, min(max_candidates, 25))

            config = _v24_9_1_ResearchLoopConfig(
                theme=str(theme or "AI infrastructure semiconductors").strip() or "AI infrastructure semiconductors",
                symbols=symbols,
                max_candidates=max_candidates,
                max_loops=1,
                min_trades=10,
                max_drawdown_limit=-0.20,
                min_sharpe=0.25,
                backend=backend,
                mode="simulation_only",
                timeframe="1d",
                repo_root=_v24_9_1_repo_root_from_store(repo_root),
            )

            try:
                result = _v24_9_1_run_research_loop(config)
                ranked = sorted(result.evaluations, key=lambda item: item.score, reverse=True)
                top_rows = []
                for item in ranked[:5]:
                    top_rows.append(
                        _v24_9_1_html.Tr([
                            _v24_9_1_html.Td(item.candidate.strategy_name),
                            _v24_9_1_html.Td(item.candidate.strategy_family),
                            _v24_9_1_html.Td(item.status),
                            _v24_9_1_html.Td(str(item.score)),
                            _v24_9_1_html.Td(str(item.aggregate_metrics.get("avg_sharpe"))),
                            _v24_9_1_html.Td(str(item.aggregate_metrics.get("worst_drawdown"))),
                            _v24_9_1_html.Td(", ".join(item.rejection_reasons[:3])),
                        ])
                    )

                report_children = [
                    _v24_9_1_html.Div(
                        className="research-loop-summary",
                        children=[
                            _v24_9_1_html.Div(f"Loop ID: {result.loop_id}"),
                            _v24_9_1_html.Div(f"Status: {result.status}"),
                            _v24_9_1_html.Div(f"Candidates: {len(result.candidates)}"),
                            _v24_9_1_html.Div(f"Survivors: {len(result.survivors)}"),
                            _v24_9_1_html.Div(f"Quant persist: {result.quant_persist_status}"),
                        ],
                    ),
                    _v24_9_1_html.Div(
                        className="research-loop-report-paths",
                        children=[
                            _v24_9_1_html.Div("Report JSON: " + str(result.report_paths.get("json", ""))),
                            _v24_9_1_html.Div("Report Markdown: " + str(result.report_paths.get("markdown", ""))),
                            _v24_9_1_html.Div("Memory feedback: " + str(result.feedback_path)),
                        ],
                    ),
                    _v24_9_1_html.Table(
                        className="research-loop-top-table",
                        children=[
                            _v24_9_1_html.Thead(
                                _v24_9_1_html.Tr([
                                    _v24_9_1_html.Th("Strategy"),
                                    _v24_9_1_html.Th("Family"),
                                    _v24_9_1_html.Th("Status"),
                                    _v24_9_1_html.Th("Score"),
                                    _v24_9_1_html.Th("Avg Sharpe"),
                                    _v24_9_1_html.Th("Worst DD"),
                                    _v24_9_1_html.Th("Reasons"),
                                ])
                            ),
                            _v24_9_1_html.Tbody(top_rows),
                        ],
                    ),
                ]

                status = (
                    f"Research loop complete. Status={result.status}; "
                    f"candidates={len(result.candidates)}; survivors={len(result.survivors)}. "
                    "Quant Dashboard refresh triggered."
                )
                return status, report_children, int(current_refresh_clicks or 0) + 1

            except Exception as exc:
                status = f"Research loop failed: {type(exc).__name__}: {exc}"
                details = _v24_9_1_html.Pre(status)
                return status, details, current_refresh_clicks or 0

        app._v24_9_1_research_loop_callbacks_registered = True

    _v24_9_1_install_research_loop_panel()
    _v24_9_1_register_research_loop_callbacks()

except Exception as _v24_9_1_research_loop_controls_exc:
    print(
        f"[v24.9.1 research loop controls] disabled: "
        f"{type(_v24_9_1_research_loop_controls_exc).__name__}: {_v24_9_1_research_loop_controls_exc}",
        flush=True,
    )
# END v24.9.1 research loop controls in quant dashboard

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

# BEGIN v24.6 direct producer wiring startup
try:
    from services.quant_schema.direct_producer_wiring import install_direct_producer_wiring
    install_direct_producer_wiring()
except Exception as _v24_6_direct_wiring_startup_exc:
    print(f"[v24.6 direct producer wiring] startup disabled: {type(_v24_6_direct_wiring_startup_exc).__name__}: {_v24_6_direct_wiring_startup_exc}")
# END v24.6 direct producer wiring startup
