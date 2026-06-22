from __future__ import annotations

"""
Dash callbacks for the Strategy-tab AI Advisor panel.

This module is intentionally advisory-only:
- no broker objects
- no order placement
- no account access
- no external tool calls
- no secrets are rendered
"""

from dash import Input, Output, State, html, no_update

from services.ai.advisor import build_ai_advisor_service
from services.ai.prompt_templates import build_prompt


def _status(text: str, tone: str = "neutral"):
    return html.Span(str(text), className=f"strategy-ai-advisor-status-pill strategy-ai-advisor-status-{tone}")


def _message_box(title: str, body: str, *, tone: str = "neutral", meta: list[str] | None = None):
    children = [
        html.Div(str(title), className=f"strategy-ai-advisor-response-title strategy-ai-advisor-{tone}"),
        html.Pre(str(body or "").strip(), className="strategy-ai-advisor-response-text"),
    ]

    if meta:
        children.append(
            html.Div(
                [html.Span(str(item), className="strategy-ai-advisor-meta-item") for item in meta],
                className="strategy-ai-advisor-meta",
            )
        )

    return html.Div(children=children, className=f"strategy-ai-advisor-response-box strategy-ai-advisor-box-{tone}")


def _clean_max_tokens(value) -> int:
    try:
        tokens = int(value)
    except Exception:
        return 300

    if tokens < 20:
        return 20

    if tokens > 1200:
        return 1200

    return tokens


def register_ai_advisor_callbacks(app) -> None:
    """
    Register the Strategy-tab AI Advisor callback.

    This callback is safe to call from app.py once the Dash app object exists.
    It uses the central AIAdvisorService, which enforces the AI safety policy.
    """
    if getattr(app, "_ai_advisor_strategy_callbacks_registered", False):
        return

    @app.callback(
        Output("strategy-ai-advisor-response", "children"),
        Output("strategy-ai-advisor-status", "children"),
        Input("strategy-ai-advisor-ask", "n_clicks"),
        State("strategy-ai-advisor-template", "value"),
        State("strategy-ai-advisor-prompt", "value"),
        State("strategy-ai-advisor-context", "value"),
        State("strategy-ai-advisor-max-output", "value"),
        prevent_initial_call=True,
    )
    def _ask_strategy_ai_advisor(n_clicks, template, prompt, context, max_output_tokens):
        if not n_clicks:
            return no_update, no_update

        clean_prompt = str(prompt or "").strip()
        clean_context = str(context or "").strip()

        if not clean_prompt and not clean_context:
            return (
                _message_box(
                    "Prompt required",
                    "Enter a strategy/backtest question or paste read-only context before asking the advisor.",
                    tone="warning",
                ),
                _status("waiting for prompt", "warning"),
            )

        try:
            built_prompt, built_context = build_prompt(
                template=template or "strategy_explain",
                user_prompt=clean_prompt,
                context=clean_context,
                metadata={"source": "strategy_tab"},
            )

            result = build_ai_advisor_service().ask(
                built_prompt,
                context=built_context,
                max_output_tokens=_clean_max_tokens(max_output_tokens),
                temperature=0.2,
            )
        except Exception as exc:
            return (
                _message_box(
                    "Advisor error",
                    str(exc),
                    tone="danger",
                ),
                _status("error", "danger"),
            )

        if not result.ok:
            tone = "warning" if result.blocked else "danger"
            label = "Blocked by safety policy" if result.blocked else "Advisor unavailable"
            reason = result.reason or "The advisor did not return a response."
            return (
                _message_box(label, reason, tone=tone),
                _status("blocked" if result.blocked else "error", tone),
            )

        meta = []
        if result.provider:
            meta.append(f"Provider: {result.provider}")
        if result.model:
            meta.append(f"Model: {result.model}")
        if result.created_at:
            meta.append(f"Created: {result.created_at}")

        return (
            _message_box(
                "Advisory response",
                result.content,
                tone="good",
                meta=meta,
            ),
            _status("response ready", "good"),
        )

    app._ai_advisor_strategy_callbacks_registered = True
