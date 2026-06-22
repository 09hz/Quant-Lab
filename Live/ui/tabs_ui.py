import os
from pathlib import Path
from dash import dcc, html
from datetime import date, timedelta


CHART_CONFIG = {
    "displaylogo": False,
    "scrollZoom": False,
    "doubleClick": "reset",
    "modeBarButtonsToRemove": [
        "lasso2d",
        "select2d",
        "autoScale2d",
    ],
}


def make_timeframe_options(timeframe_map):
    return [
        {
            "label": k,
            "value": k,
            "search": k,
        }
        for k in timeframe_map.keys()
    ]


def make_replay_speed_options():
    return [
        {"label": "0.25x", "value": 0.25, "search": "0.25x quarter slow"},
        {"label": "0.5x", "value": 0.5, "search": "0.5x half slow"},
        {"label": "1x", "value": 1, "search": "1x normal default"},
        {"label": "2x", "value": 2, "search": "2x double fast"},
        {"label": "5x", "value": 5, "search": "5x very fast"},
    ]



def make_disabled_weekend_days(years_back=10, years_forward=1):
    """
    Disable Saturdays and Sundays in Dash DatePickerSingle.
    Dash expects disabled_days as YYYY-MM-DD strings.
    """
    start = date.today() - timedelta(days=365 * years_back)
    end = date.today() + timedelta(days=365 * years_forward)

    disabled = []
    current = start

    while current <= end:
        if current.weekday() >= 5:
            disabled.append(current.isoformat())

        current += timedelta(days=1)

    return disabled


def make_chart_control_buttons(prefix: str):
    return [
        html.Button("Live", id=f"{prefix}-live-mode", n_clicks=0, className="range-btn active"),
        html.Button("1D", id=f"{prefix}-range-1d", n_clicks=0, className="range-btn"),
        html.Button("1W", id=f"{prefix}-range-1w", n_clicks=0, className="range-btn"),
        html.Button("1M", id=f"{prefix}-range-1m", n_clicks=0, className="range-btn"),
        html.Button("3M", id=f"{prefix}-range-3m", n_clicks=0, className="range-btn"),
        html.Button("1Y", id=f"{prefix}-range-1y", n_clicks=0, className="range-btn"),
        html.Button("5Y", id=f"{prefix}-range-5y", n_clicks=0, className="range-btn"),
        html.Button("Max", id=f"{prefix}-range-max", n_clicks=0, className="range-btn"),
        html.Button("Reset", id=f"{prefix}-reset-view", n_clicks=0, className="range-btn"),
    ]


def build_dashboard_tab(symbol_options, timeframe_map, default_symbol, default_timeframe):
    return html.Div(
        className="tab-panel dashboard-tab-panel",
        children=[
            html.Div(
                className="controls-row",
                children=[
                    html.Div(
                        className="control-box control-symbol",
                        children=[
                            html.Label("Instrument"),
                            dcc.Dropdown(
                                id="symbol-dropdown",
                                options=symbol_options,
                                value=default_symbol,
                                placeholder="Search ticker, symbol, or company...",
                                searchable=True,
                                clearable=False,
                                className="black-dropdown",
                            ),
                        ],
                    ),
                    html.Div(
                        className="control-box control-timeframe",
                        children=[
                            html.Label("Interval"),
                            dcc.Dropdown(
                                id="timeframe-dropdown",
                                options=make_timeframe_options(timeframe_map),
                                value=default_timeframe,
                                clearable=False,
                                searchable=True,
                                className="black-dropdown",
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(id="load-status-text", className="status-text"),
            html.Div(id="dashboard-metrics-strip", className="metrics-strip"),
            html.Div(
                className="range-row chart-control-row",
                children=make_chart_control_buttons("dashboard"),
            ),
            html.Div(
                className="chart-card",
                children=[
                    dcc.Graph(
                        id="live-chart",
                        className="chart-graph",
                        config=CHART_CONFIG,
                    ),
                ],
            ),
            html.Div(id="dashboard-stats-grid", className="stats-grid"),
        ],
    )


def _build_strategy_lab_panel():
    return html.Div(
        className="strategy-lab-panel watch-workspace-panel",
        children=[
            html.Div(
                className="strategy-lab-header",
                children=[
                    html.Div("Strategy Lab", className="strategy-lab-title"),
                    html.Div(
                        "Indicator script only · No auto-trading yet",
                        className="strategy-lab-subtitle",
                    ),
                ],
            ),
            dcc.Textarea(
                id="strategy-script-input",
                value=(
                    "fast = sma(close, 9)\n"
                    "slow = ema(close, 21)\n"
                    "\n"
                    "buy when crossover(fast, slow)\n"
                    "sell when crossunder(fast, slow)\n"
                    "\n"
                    "plot fast\n"
                    "plot slow"
                ),
                placeholder=(
                    "Example:\n"
                    "fast = sma(close, 9)\n"
                    "slow = ema(close, 21)\n"
                    "\n"
                    "buy when crossover(fast, slow)\n"
                    "sell when crossunder(fast, slow)\n"
                    "\n"
                    "plot fast\n"
                    "plot slow"
                ),
                className="strategy-script-input",
            ),
            html.Div(
                className="strategy-lab-actions",
                children=[
                    html.Button(
                        "Run Script",
                        id="strategy-run",
                        n_clicks=0,
                        className="strategy-run-btn",
                    ),
                    html.Button(
                        "Clear",
                        id="strategy-clear",
                        n_clicks=0,
                        className="strategy-clear-btn",
                    ),
                ],
            ),
            html.Div(
                id="strategy-status",
                className="strategy-status",
                children="Strategy Lab ready.",
            ),
            html.Div(
                className="strategy-backtest-panel",
                children=[
                    html.Div("Backtest", className="strategy-backtest-title"),
                    html.Div(
                        className="strategy-backtest-controls",
                        children=[
                            html.Div(
                                className="control-box strategy-backtest-input-box",
                                children=[
                                    html.Label("Initial Cash"),
                                    dcc.Input(
                                        id="backtest-initial-cash",
                                        type="number",
                                        min=100,
                                        step=100,
                                        value=100000,
                                        className="paper-input",
                                        debounce=True,
                                    ),
                                ],
                            ),
                            html.Div(
                                className="control-box strategy-backtest-input-box",
                                children=[
                                    html.Label("Quantity"),
                                    dcc.Input(
                                        id="backtest-quantity",
                                        type="number",
                                        min=1,
                                        step=1,
                                        value=10,
                                        className="paper-input",
                                        debounce=True,
                                    ),
                                ],
                            ),
                            html.Button(
                                "Run Backtest",
                                id="strategy-run-backtest",
                                n_clicks=0,
                                className="strategy-run-btn",
                            ),
                        ],
                    ),
                    html.Div(
                        id="backtest-status",
                        className="strategy-status",
                        children="Backtest ready.",
                    ),
                    html.Div(
                        id="backtest-results-panel",
                        className="backtest-results-panel",
                        children=[
                            html.Div("Run a backtest to see results.", className="paper-empty"),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="strategy-help-panel",
                children=[
                    html.Div(
                        className="strategy-help-header",
                        children=[
                            html.Div("Strategy Help", className="strategy-help-title"),
                            html.Div(
                                "Language guide, function reference, and examples",
                                className="strategy-help-subtitle",
                            ),
                        ],
                    ),
                    html.Div(
                        className="strategy-help-controls",
                        children=[
                            html.Div(
                                className="strategy-help-example-control",
                                children=[
                                    html.Label("Load Example"),
                                    dcc.Dropdown(
                                        id="strategy-example-dropdown",
                                        options=[
                                            {
                                                "label": "EMA Crossover",
                                                "value": "ema_crossover.txt",
                                            },
                                            {
                                                "label": "Fast SMA Test",
                                                "value": "sma_fast_test.txt",
                                            },
                                            {
                                                "label": "RSI Mean Reversion",
                                                "value": "rsi_mean_reversion.txt",
                                            },
                                            {
                                                "label": "Boolean Crossover",
                                                "value": "boolean_crossover.txt",
                                            },
                                            {
                                                "label": "EMA + ATR Filter",
                                                "value": "ema_supertrend.txt",
                                            },
                                            {
                                                "label": "Background Regime Filter",
                                                "value": "background_regime_test.txt",
                                            },
                                        ],
                                        value="ema_crossover.txt",
                                        clearable=False,
                                        searchable=False,
                                        className="black-dropdown",
                                    ),
                                ],
                            ),
                            html.Div(
                                className="strategy-help-button-row",
                                children=[
                                    html.Button(
                                        "Insert Example",
                                        id="strategy-insert-example",
                                        n_clicks=0,
                                        className="strategy-run-btn strategy-help-btn",
                                    ),
                                    html.Button(
                                        "Language Guide",
                                        id="strategy-show-language-guide",
                                        n_clicks=0,
                                        className="range-btn strategy-help-btn",
                                    ),
                                    html.Button(
                                        "Function Reference",
                                        id="strategy-show-function-reference",
                                        n_clicks=0,
                                        className="range-btn strategy-help-btn",
                                    ),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        id="strategy-help-content",
                        className="strategy-help-content",
                        children=[
                            html.Div(
                                "Choose an example, insert it into the editor, or open the language guide.",
                                className="paper-empty",
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


def _build_paper_trading_panel():
    return html.Div(
        className="paper-trading-panel watch-workspace-panel",
        children=[
            html.Div(
                className="paper-panel-header",
                children=[
                    html.Div("Paper Trading", className="paper-panel-title"),
                    html.Div(
                        "Simulated only · No IBKR live orders",
                        className="paper-panel-subtitle",
                    ),
                ],
            ),
            html.Div(
                className="paper-controls-row",
                children=[
                    html.Div(
                        className="control-box control-qty",
                        children=[
                            html.Label("Quantity"),
                            dcc.Input(
                                id="paper-order-qty",
                                type="number",
                                min=1,
                                step=1,
                                value=1,
                                className="paper-input",
                                debounce=True,
                            ),
                        ],
                    ),
                    html.Div(
                        className="paper-control-row",
                        children=[
                            html.Div(
                                className="paper-control-group",
                                children=[
                                    html.Label("Price Source", className="paper-control-label"),
                                    dcc.RadioItems(
                                        id="paper-price-source",
                                        options=[
                                            {"label": "Replay", "value": "replay"},
                                            {"label": "Live", "value": "live"},
                                        ],
                                        value="replay",
                                        inline=True,
                                        className="paper-radio",
                                        inputClassName="paper-radio-input",
                                        labelClassName="paper-radio-label",
                                    ),
                                ],
                            ),
                            html.Div(
                                className="paper-control-group",
                                children=[
                                    html.Label("Position Mode", className="paper-control-label"),
                                    dcc.RadioItems(
                                        id="paper-position-mode",
                                        options=[
                                            {"label": "Long Only", "value": "long_only"},
                                            {"label": "Allow Shorts", "value": "allow_shorts"},
                                        ],
                                        value="long_only",
                                        inline=True,
                                        className="paper-radio",
                                        inputClassName="paper-radio-input",
                                        labelClassName="paper-radio-label",
                                    ),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        className="paper-button-group",
                        children=[
                            html.Button("Buy", id="paper-buy", n_clicks=0, className="paper-buy-btn"),
                            html.Button("Sell", id="paper-sell", n_clicks=0, className="paper-sell-btn"),
                            html.Button(
                                "Short Buy",
                                id="paper-short-buy",
                                n_clicks=0,
                                className="paper-btn paper-short-btn hidden",
                            ),
                            html.Button(
                                "Short Sell",
                                id="paper-short-sell",
                                n_clicks=0,
                                className="paper-btn paper-short-btn hidden",
                            ),
                            html.Button(
                                "Reset Paper",
                                id="paper-reset",
                                n_clicks=0,
                                className="paper-reset-btn",
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                id="paper-trade-status",
                className="paper-trade-status",
                children="Paper account ready.",
            ),
            html.Div(
                className="paper-summary-grid",
                children=[
                    html.Div(id="paper-summary-panel", className="paper-summary-panel"),
                ],
            ),
            html.Div(
                className="paper-table-grid",
                children=[
                    html.Div(
                        className="paper-table-card",
                        children=[
                            html.Div("Positions", className="paper-table-title"),
                            html.Div(id="paper-positions-panel"),
                        ],
                    ),
                    html.Div(
                        className="paper-table-card",
                        children=[
                            html.Div("Orders", className="paper-table-title"),
                            html.Div(id="paper-orders-panel"),
                        ],
                    ),
                    html.Div(
                        className="paper-table-card",
                        children=[
                            html.Div("Fills", className="paper-table-title"),
                            html.Div(id="paper-fills-panel"),
                        ],
                    ),
                ],
            ),
        ],
    )


def _build_trade_analytics_panel():
    return html.Div(
        className="trade-analytics-panel watch-workspace-panel",
        children=[
            html.Div(
                className="trade-analytics-panel-header",
                children=[
                    html.Div("Trade Analytics", className="trade-analytics-title"),
                    html.Div(
                        "Paper trading performance summary",
                        className="trade-analytics-subtitle",
                    ),
                ],
            ),
            html.Div(
                id="trade-analytics-content",
                className="trade-analytics-content trade-analytics-content-tabbed",
                children=[
                    html.Div("No analytics loaded yet.", className="paper-empty"),
                ],
            ),
        ],
    )


def _build_watch_workspace_tabs():
    return dcc.Tabs(
        id="watch-workspace-tabs",
        value="strategy-lab",
        className="watch-workspace-tabs",
        children=[
            dcc.Tab(
                label="Strategy Lab",
                value="strategy-lab",
                className="watch-workspace-tab",
                selected_className="watch-workspace-tab-selected",
                children=[_build_strategy_lab_panel()],
            ),
            dcc.Tab(
                label="Paper Trading",
                value="paper-trading",
                className="watch-workspace-tab",
                selected_className="watch-workspace-tab-selected",
                children=[_build_paper_trading_panel()],
            ),
            dcc.Tab(
                label="Trade Analytics",
                value="trade-analytics",
                className="watch-workspace-tab",
                selected_className="watch-workspace-tab-selected",
                children=[_build_trade_analytics_panel()],
            ),
        ],
    )


def build_watch_tab(symbol_options, default_symbol, default_speed=1, default_index=100, default_date=None):
    return html.Div(
        className="tab-panel watch-tab-panel",
        children=[
            html.Div(
                className="controls-row controls-row-top",
                children=[
                    html.Div(
                        className="control-box control-symbol",
                        children=[
                            html.Label("Replay Symbol"),
                            dcc.Dropdown(
                                id="watch-symbol-dropdown",
                                options=symbol_options,
                                value=default_symbol,
                                placeholder="Search ticker, symbol, or company...",
                                searchable=True,
                                clearable=False,
                                className="black-dropdown",
                            ),
                        ],
                    ),
                    html.Div(
                        className="control-box control-timeframe",
                        children=[
                            html.Label("Interval"),
                            dcc.Dropdown(
                                id="watch-timeframe-dropdown",
                                options=[
                                    {"label": "1 Min", "value": "1 min"},
                                    {"label": "5 Min", "value": "5 min"},
                                    {"label": "15 Min", "value": "15 min"},
                                    {"label": "30 Min", "value": "30 min"},
                                    {"label": "1 Hour", "value": "1 hour"},
                                    {"label": "1 Day", "value": "1 day"},
                                ],
                                value="1 min",
                                clearable=False,
                                searchable=False,
                                className="black-dropdown",
                            ),
                        ],
                    ),
                    html.Div(
                        className="control-box control-timeframe control-speed",
                        children=[
                            html.Label("Speed"),
                            dcc.Dropdown(
                                id="replay-speed",
                                options=make_replay_speed_options(),
                                value=default_speed,
                                clearable=False,
                                searchable=True,
                                className="black-dropdown",
                            ),
                        ],
                    ),
                    html.Div(
                        className="control-box control-timeframe",
                        children=[
                            html.Label("Replay Start"),
                            dcc.DatePickerSingle(
                                id="replay-date",
                                date=default_date,
                                display_format="MM/DD/YYYY",
                                max_date_allowed=date.today(),
                                disabled_days=make_disabled_weekend_days(),
                                className="date-picker-dark",
                            ),
                        ],
                    ),
                    html.Div(
                        className="control-box control-timeframe",
                        children=[
                            html.Label("Replay End"),
                            dcc.DatePickerSingle(
                                id="replay-end-date",
                                date=default_date,
                                display_format="MM/DD/YYYY",
                                max_date_allowed=date.today(),
                                disabled_days=make_disabled_weekend_days(),
                                className="date-picker-dark",
                            ),
                        ],
                    ),
                    html.Div(
                        className="control-box",
                        children=[
                            html.Label("Replay Range"),
                            html.Button(
                                "Load Range",
                                id="replay-load-range",
                                n_clicks=0,
                                className="range-btn",
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="controls-row controls-row-bottom",
                children=[
                    html.Div(
                        className="control-box",
                        children=[
                            html.Label("Playback"),
                            html.Div(
                                [
                                    html.Button("▶ Play", id="replay-play", n_clicks=0),
                                    html.Button("⏸ Pause", id="replay-pause", n_clicks=0),
                                    html.Button("→ Step", id="replay-step", n_clicks=0),
                                    html.Button("← Rewind", id="replay-rewind", n_clicks=0),
                                ],
                                style={"display": "flex", "gap": "8px", "flexWrap": "wrap"},
                            ),
                        ],
                    ),
                    html.Div(
                        className="control-box control-symbol slider-box",
                        children=[
                            html.Label("Position"),
                            dcc.Slider(
                                id="replay-slider",
                                min=1,
                                max=100,
                                step=1,
                                value=default_index,
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(id="watch-status", className="status-text"),
            html.Div(id="watch-metrics-strip", className="metrics-strip"),
            html.Div(
                className="range-row chart-control-row",
                children=make_chart_control_buttons("watch"),
            ),
            html.Div(
                className="chart-card watch-chart-wrap",
                children=[
                    html.Div(
                        id="watch-loading-overlay",
                        className="watch-loading-overlay",
                        children=[
                            html.Div("Preparing replay data...", className="watch-loading-text"),
                        ],
                    ),
                    dcc.Graph(
                        id="watch-chart",
                        className="chart-graph",
                        config=CHART_CONFIG,
                    ),
                ],
            ),
            html.Div(id="watch-stats-grid", className="stats-grid"),
            _build_watch_workspace_tabs(),
        ],
    )


def build_quotes_tab(symbol_options, default_symbol):
    return html.Div(
        className="tab-panel quotes-tab-panel",
        children=[
            html.Div(
                className="controls-row",
                children=[
                    html.Div(
                        className="control-box control-symbol",
                        children=[
                            html.Label("Instrument"),
                            dcc.Dropdown(
                                id="quotes-symbol-dropdown",
                                options=symbol_options,
                                value=default_symbol,
                                placeholder="Search ticker, symbol, or company...",
                                searchable=True,
                                clearable=False,
                                className="black-dropdown",
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(id="quotes-status", className="status-text"),
            html.Div(
                className="chart-card",
                children=[
                    html.Div(
                        id="quotes-panel",
                        className="quote-strip",
                        children="Ready for quotes",
                    ),
                ],
            ),
        ],
    )

# =============================================================================
# Settings tab foundation (Patch 09)
# =============================================================================

def _settings_env_value(name: str, default: str = "not set", *, mask: bool = False) -> str:
    """
    Return a display-safe environment setting.

    Secrets are never rendered directly into the Dash page.
    """
    try:
        value = os.getenv(name)
    except Exception:
        value = None

    if value is None or str(value).strip() == "":
        return default

    if mask:
        return "configured (hidden)"

    return str(value)


def _settings_bool_text(value: bool) -> str:
    return "Yes" if bool(value) else "No"


def _settings_env_bool(name: str, default: bool = False) -> bool:
    """
    Parse a boolean environment variable safely.
    """
    try:
        value = os.getenv(name)
    except Exception:
        value = None

    if value is None or str(value).strip() == "":
        return bool(default)

    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _settings_row(label: str, value, note: str | None = None):
    children = [
        html.Div(str(label), className="settings-label"),
        html.Div(str(value), className="settings-value"),
    ]

    if note:
        children.append(html.Div(str(note), className="settings-note"))

    return html.Div(className="settings-row", children=children)


def _settings_command(text: str):
    return html.Code(str(text), className="settings-command")


def _settings_status_pill(text: str, tone: str = "neutral"):
    return html.Span(str(text), className=f"settings-status-pill settings-status-{tone}")


def _settings_lock_row(label: str, enabled: bool, *, safe_when: bool = False, note: str | None = None):
    """
    Render a future-AI safety lock row.

    safe_when means the value that should be considered the safe state.
    Example:
        AI_ALLOW_ORDER_PLACEMENT=false is safe, so safe_when=False.
        AI_ADVISORY_ONLY=true is safe, so safe_when=True.
    """
    is_safe = bool(enabled) is bool(safe_when)
    tone = "good" if is_safe else "danger"
    value_text = "ON" if enabled else "OFF"

    children = [
        html.Div(str(label), className="settings-lock-label"),
        html.Div(
            children=[
                _settings_status_pill(value_text, tone),
                html.Span(" safe" if is_safe else " review", className=f"settings-lock-text settings-lock-{tone}"),
            ],
            className="settings-lock-value",
        ),
    ]

    if note:
        children.append(html.Div(str(note), className="settings-lock-note"))

    return html.Div(className="settings-lock-row", children=children)


def _settings_cache_summary(root_text: str) -> dict:
    """
    Return a lightweight local data cache summary.

    This only counts files and size. It does not parse CSV data and should stay
    fast enough to run during Dash layout construction.
    """
    root = Path(str(root_text or "cache/replay")).expanduser()

    if not root.is_absolute():
        root = Path.cwd() / root

    summary = {
        "root": str(root),
        "exists": root.exists(),
        "files": 0,
        "bytes": 0,
    }

    if not root.exists():
        return summary

    extensions = {".csv", ".parquet", ".pq", ".feather"}

    try:
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in extensions:
                summary["files"] += 1
                try:
                    summary["bytes"] += path.stat().st_size
                except OSError:
                    pass
    except Exception:
        # Avoid breaking app startup just because a cache path cannot be read.
        pass

    return summary


def _settings_format_bytes(value: int) -> str:
    try:
        size = float(value)
    except Exception:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB"]
    unit = 0

    while size >= 1024 and unit < len(units) - 1:
        size /= 1024
        unit += 1

    if unit == 0:
        return f"{int(size)} {units[unit]}"

    return f"{size:.2f} {units[unit]}"


def _settings_build_ai_lock_card():
    """
    Read-only future AI safety settings.

    These controls are intentionally display-only. Runtime AI switching and
    secret editing should not happen in Dash browser state.
    """
    ai_enabled = _settings_env_bool("AI_FEATURES_ENABLED", False)
    ai_advisory_only = _settings_env_bool("AI_ADVISORY_ONLY", True)
    ai_allow_orders = _settings_env_bool("AI_ALLOW_ORDER_PLACEMENT", False)
    ai_allow_broker_access = _settings_env_bool("AI_ALLOW_BROKER_ACCESS", False)
    ai_allow_external_tools = _settings_env_bool("AI_ALLOW_EXTERNAL_TOOLS", False)
    ai_require_confirmation = _settings_env_bool("AI_REQUIRE_HUMAN_CONFIRMATION", True)

    llm_provider = _settings_env_value("LLM_PROVIDER", "none")
    llm_base_url = _settings_env_value("LLM_BASE_URL", "not configured")
    openai_key = _settings_env_value("OPENAI_API_KEY", "not configured", mask=True)

    if not ai_enabled:
        ai_state = _settings_status_pill("AI disabled", "good")
    elif ai_advisory_only and not ai_allow_orders and not ai_allow_broker_access:
        ai_state = _settings_status_pill("AI advisory-only", "warn")
    else:
        ai_state = _settings_status_pill("AI needs review", "danger")

    return html.Div(
        className="settings-card settings-ai-lock-card",
        children=[
            html.Div(
                className="settings-card-title-row",
                children=[
                    html.Div("Future AI Safety Locks", className="settings-card-title"),
                    ai_state,
                ],
            ),
            html.Div(
                "This section is read-only. It reserves a safe place for future AI controls without enabling AI trading.",
                className="settings-card-description",
            ),
            _settings_row("LLM provider", llm_provider),
            _settings_row("LLM base URL", llm_base_url, "Use localhost/LAN only until authentication exists."),
            _settings_row("OpenAI API key", openai_key, "Masked. Never show API keys in the browser."),
            html.Div(className="settings-lock-list", children=[
                _settings_lock_row(
                    "AI features",
                    ai_enabled,
                    safe_when=False,
                    note="Default safe state is OFF.",
                ),
                _settings_lock_row(
                    "Advisory-only mode",
                    ai_advisory_only,
                    safe_when=True,
                    note="AI may explain/suggest, but should not execute.",
                ),
                _settings_lock_row(
                    "Order placement allowed",
                    ai_allow_orders,
                    safe_when=False,
                    note="Must remain OFF until broker-safety code and confirmations exist.",
                ),
                _settings_lock_row(
                    "Broker/account access",
                    ai_allow_broker_access,
                    safe_when=False,
                    note="Must remain OFF until explicit permission gates exist.",
                ),
                _settings_lock_row(
                    "External tools/network actions",
                    ai_allow_external_tools,
                    safe_when=False,
                    note="Must remain OFF until allowlists and audit logs exist.",
                ),
                _settings_lock_row(
                    "Human confirmation required",
                    ai_require_confirmation,
                    safe_when=True,
                    note="Should remain ON for any future AI-assisted action.",
                ),
            ]),
        ],
    )


def build_charts_tab(symbol_options, timeframe_map, default_symbol, default_timeframe):
    """
    Compatibility name.

    The old Charts tab is now the Settings tab. The function name is intentionally
    kept as build_charts_tab so existing app imports do not break.
    """
    provider = _settings_env_value("MARKET_DATA_PROVIDER", "ibkr")
    csv_root = _settings_env_value("CSV_MARKET_DATA_ROOT", "cache/replay")
    ibkr_host = _settings_env_value("IBKR_HOST", "127.0.0.1")
    ibkr_port = _settings_env_value("IBKR_PORT", "not set")
    ibkr_client_id = _settings_env_value("IBKR_CLIENT_ID", "not set")
    tradier_env = _settings_env_value("TRADIER_ENV", "sandbox")
    tradier_token = _settings_env_value("TRADIER_ACCESS_TOKEN", "not configured", mask=True)

    cache = _settings_cache_summary(csv_root)

    return html.Div(
        className="tab-panel settings-tab-panel",
        children=[
            html.Div(
                className="settings-header",
                children=[
                    html.Div("Settings", className="settings-title"),
                    html.Div(
                        "Read-only app configuration, provider status, local data summary, and future safety locks.",
                        className="settings-subtitle",
                    ),
                ],
            ),

            html.Div(
                className="settings-grid",
                children=[
                    html.Div(
                        className="settings-card",
                        children=[
                            html.Div("Market Data Provider", className="settings-card-title"),
                            _settings_row("Active provider", provider),
                            _settings_row("CSV cache root", csv_root),
                            _settings_row(
                                "Provider selection",
                                "Restart required",
                                "For now, change MARKET_DATA_PROVIDER before launching Dash.",
                            ),
                        ],
                    ),

                    html.Div(
                        className="settings-card",
                        children=[
                            html.Div("IBKR / Gateway", className="settings-card-title"),
                            _settings_row("Host", ibkr_host),
                            _settings_row("Port", ibkr_port, "Your Gateway live port is commonly 4001."),
                            _settings_row("Client ID", ibkr_client_id),
                            _settings_row(
                                "Connection note",
                                "External",
                                "IB Gateway/TWS must be running for exports or live IBKR data.",
                            ),
                        ],
                    ),

                    html.Div(
                        className="settings-card",
                        children=[
                            html.Div("Tradier", className="settings-card-title"),
                            _settings_row("Environment", tradier_env),
                            _settings_row("Access token", tradier_token),
                            _settings_row(
                                "Status",
                                "Scaffold only",
                                "Do not enable Tradier until the account/API token is ready.",
                            ),
                        ],
                    ),

                    html.Div(
                        className="settings-card",
                        children=[
                            html.Div("Local Data Cache", className="settings-card-title"),
                            _settings_row("Root path", cache["root"]),
                            _settings_row("Exists", _settings_bool_text(cache["exists"])),
                            _settings_row("Data files", cache["files"]),
                            _settings_row("Approx size", _settings_format_bytes(cache["bytes"])),
                        ],
                    ),
                ],
            ),

            _settings_build_ai_lock_card(),

            html.Div(
                className="settings-card settings-wide-card",
                children=[
                    html.Div("Useful Commands", className="settings-card-title"),
                    html.Div("Inspect cache:", className="settings-command-label"),
                    _settings_command("python .\\Live\\scripts\\inspect_market_data_cache.py"),
                    html.Div("Check active provider:", className="settings-command-label"),
                    _settings_command(
                        "python .\\Live\\scripts\\check_market_data_provider.py "
                        "--provider csv --symbol MSFT --timeframe \"1 min\""
                    ),
                    html.Div("Export IB Gateway history:", className="settings-command-label"),
                    _settings_command(
                        "python .\\Live\\scripts\\export_ibkr_history_to_csv.py "
                        "--symbol MSFT --timeframe \"1 min\" --start 2026-06-15 "
                        "--end 2026-06-19 --port 4001 --client-id 31"
                    ),
                ],
            ),

            html.Div(
                className="settings-card settings-wide-card settings-security-card",
                children=[
                    html.Div("Security Rules", className="settings-card-title"),
                    html.Ul(
                        children=[
                            html.Li("Never commit .env or real API tokens."),
                            html.Li("Secrets are masked in this tab and should stay out of browser storage."),
                            html.Li("Provider switching remains restart-based until a safe runtime config layer exists."),
                            html.Li("This Settings tab is read-only; it does not place orders or change broker state."),
                            html.Li("Future AI features must stay advisory-only until explicit safety gates exist."),
                            html.Li("AI code must never call broker/order functions directly."),
                        ],
                    ),
                ],
            ),

            # Legacy hidden Charts IDs.
            #
            # Existing callbacks may still reference these old IDs. Keeping them
            # hidden avoids breaking callback registration while the visible tab
            # becomes Settings.
            html.Div(
                className="settings-legacy-charts-hidden",
                style={"display": "none"},
                children=[
                    dcc.Dropdown(
                        id="charts-symbol-dropdown",
                        options=symbol_options,
                        value=default_symbol,
                        searchable=True,
                        clearable=False,
                    ),
                    dcc.Dropdown(
                        id="charts-timeframe-dropdown",
                        options=make_timeframe_options(timeframe_map),
                        value=default_timeframe,
                        clearable=False,
                        searchable=True,
                    ),
                    html.Div(id="charts-status"),
                    dcc.Graph(
                        id="charts-main-graph",
                        config=CHART_CONFIG,
                    ),
                ],
            ),
        ],
    )

# =============================================================================
# End Settings tab foundation (Patch 09)
# =============================================================================
