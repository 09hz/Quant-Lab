from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from dash import html


TRUE_VALUES = {"1", "true", "yes", "y", "on", "enabled"}


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None or str(value).strip() == "":
        return default
    return str(value).strip()


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in TRUE_VALUES


def _masked_status(name: str) -> str:
    value = os.getenv(name)
    if value and str(value).strip():
        return "configured"
    return "not configured"


def _status_badge(label: str, ok: bool, safe_when_false: bool = False) -> html.Span:
    if ok:
        cls = "settings-pill settings-pill-on"
        text = "ON"
    else:
        cls = "settings-pill settings-pill-safe" if safe_when_false else "settings-pill settings-pill-off"
        text = "OFF"
    return html.Span(text, className=cls, title=label)


def _setting_row(label: str, value: Any, note: str = "") -> html.Div:
    return html.Div(
        [
            html.Div(label, className="settings-title"),
            html.Div(str(value), className="settings-row-value"),
            html.Div(note, className="settings-row-note") if note else html.Div("", className="settings-row-note"),
        ],
        className="settings-row",
    )


def _lock_row(label: str, enabled: bool, note: str, safe_when_false: bool = True) -> html.Div:
    return html.Div(
        [
            html.Div(label, className="settings-title"),
            html.Div(_status_badge(label, enabled, safe_when_false=safe_when_false), className="settings-muted"),
            html.Div(note, className="settings-row-note"),
        ],
        className="settings-row",
    )


def _section(title: str, children: list[Any], subtitle: str = "") -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    html.H3(title, className="settings-title"),
                    html.Div(subtitle, className="settings-muted") if subtitle else None,
                ],
                className="settings-section-header",
            ),
            html.Div(children, className="settings-section-body"),
        ],
        className="settings-section",
    )


def _ai_mode_label() -> str:
    if not _bool_env("AI_FEATURES_ENABLED", False):
        return "AI disabled"
    if _bool_env("AI_ADVISORY_ONLY", True):
        return "AI advisory-only"
    return "AI enabled"


def build_settings_tab() -> html.Div:
    ai_enabled = _bool_env("AI_FEATURES_ENABLED", False)
    advisory_only = _bool_env("AI_ADVISORY_ONLY", True)
    order_allowed = _bool_env("AI_ALLOW_ORDER_PLACEMENT", False)
    broker_allowed = _bool_env("AI_ALLOW_BROKER_ACCESS", False)
    external_tools = _bool_env("AI_ALLOW_EXTERNAL_TOOLS", False)
    human_confirm = _bool_env("AI_REQUIRE_HUMAN_CONFIRMATION", True)

    provider = _env("MARKET_DATA_PROVIDER", "ibkr")
    csv_root = _env("CSV_MARKET_DATA_ROOT", "cache/replay")
    ibkr_host = _env("IBKR_HOST", "127.0.0.1")
    ibkr_port = _env("IBKR_PORT", "4001")
    ibkr_client = _env("IBKR_CLIENT_ID", "")

    llm_provider = _env("LLM_PROVIDER", "none")
    llm_base_url = _env("LLM_BASE_URL", "not configured")
    llm_model = _env("LLM_MODEL", "not configured")
    token_param = _env("LLM_CHAT_TOKEN_PARAM", "auto")
    send_temp = _env("LLM_SEND_TEMPERATURE", "auto")

    return html.Div(
        [
            html.Div(
                [
                    html.H2("Settings", className="settings-title"),
                    html.Div(_ai_mode_label(), className="settings-mode-badge"),
                    html.P(
                        "Read-only configuration and safety locks. Change values in .env or your run environment, then restart the app.",
                        className="settings-muted",
                    ),
                ],
                className="settings-hero",
            ),
            _section(
                "Market Data",
                [
                    _setting_row("Active provider", provider),
                    _setting_row("CSV cache root", csv_root),
                    _setting_row("IBKR host", ibkr_host),
                    _setting_row("IBKR port", ibkr_port),
                    _setting_row("IBKR client ID", ibkr_client or "not configured"),
                    _setting_row("Tradier token", _masked_status("TRADIER_ACCESS_TOKEN"), "Masked; never shown in browser."),
                ],
                "Provider selection and local data paths.",
            ),
            _section(
                "Future AI Safety Locks",
                [
                    _setting_row("LLM provider", llm_provider),
                    _setting_row("LLM base URL", llm_base_url, "Use localhost/LAN only until authentication exists for local servers."),
                    _setting_row("LLM model", llm_model),
                    _setting_row("LLM token parameter", token_param),
                    _setting_row("LLM temperature behavior", send_temp),
                    _setting_row("OpenAI API key", _masked_status("OPENAI_API_KEY"), "Masked. Never show API keys in the browser."),
                    _lock_row("AI features", ai_enabled, "Default safe state is OFF.", safe_when_false=True),
                    _lock_row("Advisory-only mode", advisory_only, "AI may explain/suggest, but should not execute.", safe_when_false=False),
                    _lock_row("Order placement allowed", order_allowed, "Must remain OFF until broker-safety code and confirmations exist.", safe_when_false=True),
                    _lock_row("Broker/account access", broker_allowed, "Must remain OFF until explicit permission gates exist.", safe_when_false=True),
                    _lock_row("External tools/network actions", external_tools, "Must remain OFF until allowlists and audit logs exist.", safe_when_false=True),
                    _lock_row("Human confirmation required", human_confirm, "Should remain ON for any future AI-assisted action.", safe_when_false=False),
                ],
                "This section reserves a safe place for future AI controls without enabling AI trading.",
            ),
            _section(
                "Runtime",
                [
                    _setting_row("Generated at", datetime.now().isoformat(timespec="seconds")),
                    _setting_row("Working directory", str(Path.cwd())),
                    _setting_row("Python", sys.executable),
                ],
                "What this Dash process sees right now.",
            ),
        ],
        className="settings-tab",
        id="settings-tab",
    )


def build_charts_tab() -> html.Div:
    return build_settings_tab()
