"""
Reusable advisory AI prompt templates.

These templates are intentionally read-only. They should never include API keys,
broker credentials, or direct order-placement instructions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AdvisorTemplate:
    name: str
    title: str
    prompt: str
    expected_context: str = ""


TEMPLATES: dict[str, AdvisorTemplate] = {
    "general": AdvisorTemplate(
        name="general",
        title="General advisory question",
        prompt=(
            "Answer this trading-app question in an advisory-only way. "
            "Do not place trades or imply broker access."
        ),
        expected_context="Optional logs, settings, or chart notes.",
    ),
    "provider_status": AdvisorTemplate(
        name="provider_status",
        title="Explain provider/data status",
        prompt=(
            "Explain the market-data provider status below. Identify what is working, "
            "what is blocked, and the safest next debugging step. Do not request secrets."
        ),
        expected_context="Provider diagnostic output or Settings status.",
    ),
    "backtest_summary": AdvisorTemplate(
        name="backtest_summary",
        title="Summarize a backtest",
        prompt=(
            "Summarize this backtest result. Mention realized PnL, number of trades if "
            "available, obvious risks, and what should be checked before trusting it. "
            "Do not recommend live trading."
        ),
        expected_context="Backtest metrics, trade log, or PnL summary.",
    ),
    "strategy_explain": AdvisorTemplate(
        name="strategy_explain",
        title="Explain a strategy",
        prompt=(
            "Explain this strategy or signal logic in plain English. Identify assumptions, "
            "possible false signals, and safe validation steps. Do not generate live orders."
        ),
        expected_context="Strategy text, indicator settings, or signal log.",
    ),
    "error_debug": AdvisorTemplate(
        name="error_debug",
        title="Debug an app error",
        prompt=(
            "Explain this app error and suggest practical debugging steps. Focus on likely "
            "root causes and safe fixes. Do not ask for API keys or secrets."
        ),
        expected_context="Traceback, console log, or screenshot notes.",
    ),
}


def list_template_names() -> list[str]:
    return sorted(TEMPLATES.keys())


def get_template(name: str | None) -> AdvisorTemplate:
    key = str(name or "general").strip().lower()
    if key not in TEMPLATES:
        valid = ", ".join(list_template_names())
        raise ValueError(f"Unknown advisor template {name!r}. Valid templates: {valid}")
    return TEMPLATES[key]


def build_prompt(
    *,
    template: str | None = "general",
    user_prompt: str = "",
    context: str = "",
    metadata: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """
    Build a prompt/context pair for AIAdvisorService.ask().

    Returns:
        (prompt, context)
    """
    item = get_template(template)
    clean_prompt = str(user_prompt or "").strip()
    clean_context = str(context or "").strip()

    prompt_parts = [item.prompt]

    if clean_prompt:
        prompt_parts.append("")
        prompt_parts.append("User question:")
        prompt_parts.append(clean_prompt)

    if metadata:
        prompt_parts.append("")
        prompt_parts.append("Metadata:")
        for key in sorted(metadata):
            value = metadata[key]
            prompt_parts.append(f"- {key}: {value}")

    return "\n".join(prompt_parts).strip(), clean_context
