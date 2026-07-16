from __future__ import annotations

from dash import Input, Output, html

from services.market_calendar.live_trading_day import get_watch_live_trading_day_status


def _build_guard_banner(status):
    title = "Live mode available" if status.allowed else "Live mode disabled"
    detail = f"{status.today} ({status.weekday}) - {status.reason}"
    if not status.allowed:
        detail = detail + " Use Replay or CSV/local data."

    return html.Div(
        [
            html.Span(title, className="watch-live-guard-title"),
            html.Span(detail, className="watch-live-guard-detail"),
        ],
        className="watch-live-guard-inner",
    )


def register_watch_live_guard_callbacks(app):
    @app.callback(
        Output("watch-live-guard-banner", "children"),
        Output("watch-live-guard-banner", "className"),
        Output("watch-symbol-dropdown", "disabled"),
        Output("watch-timeframe-dropdown", "disabled"),
        Input("ui-interval", "n_intervals"),
    )
    def _watch_live_guard(_n_intervals):
        status = get_watch_live_trading_day_status()
        class_name = (
            "watch-live-guard-banner watch-live-guard-open"
            if status.allowed
            else "watch-live-guard-banner watch-live-guard-closed"
        )
        disabled = not status.allowed
        return _build_guard_banner(status), class_name, disabled, disabled
