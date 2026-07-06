from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from dash import Input, Output, State, dcc
from dash.exceptions import PreventUpdate

try:
    from services.ai.current_strategy_context import (
        build_strategy_runtime_context,
    )
except Exception:
    build_strategy_runtime_context = None

try:
    from services.exports.export_manager import redact_secrets
except Exception:
    def redact_secrets(value: str) -> str:
        return value


def _children_to_text(value: Any) -> str:
    # Convert Dash children/props to readable text for AI/export context.
    if value is None:
        return ""

    if isinstance(value, str):
        return value

    if isinstance(value, (int, float, bool)):
        return str(value)

    if isinstance(value, list):
        parts = [_children_to_text(item) for item in value]
        return "\n".join(part for part in parts if part)

    if isinstance(value, dict):
        props = value.get("props")
        if isinstance(props, dict) and "children" in props:
            return _children_to_text(props.get("children"))

        try:
            return json.dumps(value, indent=2, default=str)
        except Exception:
            return str(value)

    return str(value)


def _summarize_chart_state(chart_state: Any) -> str:
    if not chart_state:
        return "not available"

    try:
        if isinstance(chart_state, str):
            chart_state = json.loads(chart_state)
    except Exception:
        pass

    if isinstance(chart_state, dict):
        keys = sorted(str(k) for k in chart_state.keys())
        return "available; keys=" + ", ".join(keys[:20])

    return f"available; type={type(chart_state).__name__}"


def _build_context_text(
    *,
    strategy_script: Any,
    symbol: Any,
    timeframe: Any,
    replay_start: Any,
    replay_end: Any,
    initial_cash: Any,
    quantity: Any,
    backtest_results: Any,
    dashboard_chart_state: Any,
    watch_chart_state: Any,
) -> str:
    script_text = redact_secrets(str(strategy_script or "").strip())
    backtest_text = redact_secrets(_children_to_text(backtest_results).strip())

    if build_strategy_runtime_context is not None:
        try:
            ctx = build_strategy_runtime_context(
                strategy_script=script_text,
                symbol=symbol,
                timeframe=timeframe,
                start=replay_start,
                end=replay_end,
                initial_cash=initial_cash,
                quantity=quantity,
                backtest_summary=backtest_text,
                metadata={
                    "source": "strategy_ai_context_ui",
                    "dashboard_chart_state": _summarize_chart_state(dashboard_chart_state),
                    "watch_chart_state": _summarize_chart_state(watch_chart_state),
                },
            )
            for method_name in ("to_ai_context", "to_markdown", "to_markdown_text"):
                method = getattr(ctx, method_name, None)
                if callable(method):
                    return str(method())
        except Exception:
            pass

    parts = [
        "# Current Strategy Context",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Market Selection",
        f"- Symbol: {symbol or 'not selected'}",
        f"- Timeframe: {timeframe or 'not selected'}",
        f"- Replay/Backtest Start: {replay_start or 'not selected'}",
        f"- Replay/Backtest End: {replay_end or 'not selected'}",
        "",
        "## Backtest Settings",
        f"- Initial Cash: {initial_cash if initial_cash not in (None, '') else 'not set'}",
        f"- Quantity: {quantity if quantity not in (None, '') else 'not set'}",
        "",
        "## Bars / Chart State Summary",
        f"- Dashboard chart state: {_summarize_chart_state(dashboard_chart_state)}",
        f"- Watch chart state: {_summarize_chart_state(watch_chart_state)}",
        "",
        "## Strategy Script",
        "```",
        script_text or "# No strategy script entered.",
        "```",
        "",
        "## Current Backtest Results",
        backtest_text or "No backtest result is currently attached. Run a backtest first for result-aware analysis.",
        "",
        "## Safety Instruction",
        "Use this context for advisory analysis only. Do not place orders, request broker credentials, or imply execution.",
    ]
    return "\n".join(parts)



def _merge_context_text(existing_context: Any, new_context: Any, *, max_chars: int = 24000) -> str:
    # Append strategy/research context instead of replacing the current AI context box.
    existing = redact_secrets(str(existing_context or "").strip())
    new = redact_secrets(str(new_context or "").strip())

    if not new:
        return existing
    if not existing:
        return new
    if new in existing:
        return existing

    combined = existing + "\n\n---\n\n# Attached Context Update\n\n" + new
    if len(combined) <= max_chars:
        return combined

    keep_tail = max_chars - 180
    if keep_tail < 1000:
        keep_tail = max_chars
    return (
        "[Older attached context truncated to keep Strategy AI context size safe]\n\n"
        + combined[-keep_tail:].lstrip()
    )


def _build_payload(
    strategy_script: Any,
    symbol: Any,
    timeframe: Any,
    replay_start: Any,
    replay_end: Any,
    initial_cash: Any,
    quantity: Any,
    backtest_results: Any,
    dashboard_chart_state: Any,
    watch_chart_state: Any,
) -> dict[str, Any]:
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "symbol": symbol,
        "timeframe": timeframe,
        "replay_start": replay_start,
        "replay_end": replay_end,
        "initial_cash": initial_cash,
        "quantity": quantity,
        "strategy_script": redact_secrets(str(strategy_script or "")),
        "backtest_results_text": redact_secrets(_children_to_text(backtest_results)),
        "dashboard_chart_state_summary": _summarize_chart_state(dashboard_chart_state),
        "watch_chart_state_summary": _summarize_chart_state(watch_chart_state),
        "safety": {
            "advisory_only": True,
            "broker_access": False,
            "order_placement": False,
        },
    }


def _safe_filename(symbol: Any, timeframe: Any, suffix: str) -> str:
    raw_symbol = str(symbol or "strategy").upper().strip()
    raw_tf = str(timeframe or "timeframe").lower().replace(" ", "_").replace("/", "_")
    safe_symbol = "".join(ch for ch in raw_symbol if ch.isalnum() or ch in ("-", "_")) or "strategy"
    safe_tf = "".join(ch for ch in raw_tf if ch.isalnum() or ch in ("-", "_")) or "timeframe"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{safe_symbol}_{safe_tf}_context_{stamp}.{suffix}"


def register_strategy_ai_context_callbacks(app) -> None:
    # Register Strategy Lab context attach/export callbacks.

    context_states = [
        State("strategy-script-input", "value"),
        State("symbol-dropdown", "value"),
        State("timeframe-dropdown", "value"),
        State("replay-date", "date"),
        State("replay-end-date", "date"),
        State("backtest-initial-cash", "value"),
        State("backtest-quantity", "value"),
        State("backtest-results-panel", "children"),
        State("dashboard-chart-state", "data"),
        State("watch-chart-state", "data"),
    ]

    @app.callback(
        Output("strategy-ai-advisor-context", "value"),
        Output("strategy-ai-context-status", "children"),
        Input("strategy-ai-context-attach", "n_clicks"),
        Input("strategy-ai-context-clear", "n_clicks"),
        State("strategy-ai-advisor-context", "value"),
        *context_states,
        prevent_initial_call=True,
    )
    def attach_or_clear_context(
        attach_clicks,
        clear_clicks,
        existing_context,
        strategy_script,
        symbol,
        timeframe,
        replay_start,
        replay_end,
        initial_cash,
        quantity,
        backtest_results,
        dashboard_chart_state,
        watch_chart_state,
    ):
        from dash import callback_context

        trigger = callback_context.triggered[0]["prop_id"].split(".")[0] if callback_context.triggered else ""

        if trigger == "strategy-ai-context-clear":
            return "", "Attached context cleared."

        if trigger != "strategy-ai-context-attach":
            raise PreventUpdate

        context_text = _build_context_text(
            strategy_script=strategy_script,
            symbol=symbol,
            timeframe=timeframe,
            replay_start=replay_start,
            replay_end=replay_end,
            initial_cash=initial_cash,
            quantity=quantity,
            backtest_results=backtest_results,
            dashboard_chart_state=dashboard_chart_state,
            watch_chart_state=watch_chart_state,
        )

        merged_context = _merge_context_text(existing_context, context_text)
        appended = bool(str(existing_context or "").strip())
        status = (
            f"{'Appended' if appended else 'Attached'} current Strategy context for {symbol or 'unknown symbol'} "
            f"({timeframe or 'unknown timeframe'}). "
            "Backtest results are included if currently visible. Clear Context is the only UI action that resets this stack."
        )
        return merged_context, status

    @app.callback(
        Output("strategy-context-download-json", "data"),
        Input("strategy-export-context-json", "n_clicks"),
        *context_states,
        prevent_initial_call=True,
    )
    def export_strategy_context_json(
        n_clicks,
        strategy_script,
        symbol,
        timeframe,
        replay_start,
        replay_end,
        initial_cash,
        quantity,
        backtest_results,
        dashboard_chart_state,
        watch_chart_state,
    ):
        if not n_clicks:
            raise PreventUpdate

        payload = _build_payload(
            strategy_script,
            symbol,
            timeframe,
            replay_start,
            replay_end,
            initial_cash,
            quantity,
            backtest_results,
            dashboard_chart_state,
            watch_chart_state,
        )
        text = json.dumps(payload, indent=2, default=str)
        return dcc.send_string(text, _safe_filename(symbol, timeframe, "json"))

    @app.callback(
        Output("strategy-context-download-md", "data"),
        Input("strategy-export-context-md", "n_clicks"),
        *context_states,
        prevent_initial_call=True,
    )
    def export_strategy_context_markdown(
        n_clicks,
        strategy_script,
        symbol,
        timeframe,
        replay_start,
        replay_end,
        initial_cash,
        quantity,
        backtest_results,
        dashboard_chart_state,
        watch_chart_state,
    ):
        if not n_clicks:
            raise PreventUpdate

        text = _build_context_text(
            strategy_script=strategy_script,
            symbol=symbol,
            timeframe=timeframe,
            replay_start=replay_start,
            replay_end=replay_end,
            initial_cash=initial_cash,
            quantity=quantity,
            backtest_results=backtest_results,
            dashboard_chart_state=dashboard_chart_state,
            watch_chart_state=watch_chart_state,
        )
        return dcc.send_string(text, _safe_filename(symbol, timeframe, "md"))
