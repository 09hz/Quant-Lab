from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyLanguageViolation:
    label: str
    detail: str


SCRIPT_INTENT_RE = re.compile(
    r"\b("
    r"script|strategy|improve|optimi[sz]e|rewrite|fix|debug|refactor|"
    r"minimal diff|script only|backtest|signal|entry|exit"
    r")\b",
    re.IGNORECASE,
)

VIOLATION_PATTERNS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "imports",
        "The Strategy Lab script should not import modules. Use the app's built-in strategy helpers and existing script style.",
        re.compile(r"(?m)^\s*(import|from)\s+\S+"),
    ),
    (
        "custom strategy engine function",
        "Do not define strategy_script(), a pandas backtester, or a separate engine. Edit the app-compatible script directly.",
        re.compile(r"(?m)^\s*def\s+strategy_script\s*\("),
    ),
    (
        "pandas/numpy direct use",
        "Do not write pandas/numpy code for Strategy Lab output unless the attached app language guide explicitly shows it.",
        re.compile(r"\b(pd|np|pandas|numpy)\b", re.IGNORECASE),
    ),
    (
        "file/network access",
        "Strategy scripts must not read files, open sockets, call URLs, or access environment variables.",
        re.compile(r"\b(open\(|requests\.|urllib|socket|os\.environ|subprocess|Path\()", re.IGNORECASE),
    ),
    (
        "broker/order access",
        "AI output must remain advisory-only and must not call broker/order APIs.",
        re.compile(r"\b(place_order|submit_order|ib\.|IB\(|market_order|limit_order|bracket_order)\b", re.IGNORECASE),
    ),
)


CORE_STRATEGY_LANGUAGE_REFERENCE = """\
## App Strategy Lab language reference

The Strategy Lab script editor is not a blank Python notebook. Treat it as the app's restricted strategy-script language.

Hard rules:
- Do not use imports.
- Do not use pandas, numpy, requests, pathlib, os, subprocess, files, sockets, or environment variables.
- Do not define strategy_script(), classes, a new backtesting engine, or a custom broker wrapper.
- Do not place orders, access IBKR, access accounts, or imply broker execution.
- Do not assume hidden files, API keys, broker state, or external browsing.
- Preserve the user's existing app-compatible script style when editing.
- Use the attached current strategy/backtest/research context as read-only context.

When the user asks to improve, rewrite, optimize, debug, or fix a Strategy Lab script:
- Return an app-compatible Strategy Lab script, not generic pandas/numpy Python.
- Prefer a minimal edit to the attached/current script unless the user asks for a full rewrite.
- Keep indicators, variables, entries, exits, and risk filters in the same language style used by the current script.
- If the required function names are unclear, ask for the Strategy Lab function reference instead of inventing a new API.
- For "script only" requests, return only the script text with no explanation and no markdown fence.

Wrong output examples:
- import numpy as np
- import pandas as pd
- def strategy_script(df, cash, ...):
- code that returns a dict of pandas columns
- code that calls broker/order/network/file APIs

Better behavior:
- Edit the script already attached in the context.
- Keep the output compatible with the Strategy Lab editor.
- Mention limitations only when the user asks for explanation.
"""


def is_strategy_script_intent(*parts: object) -> bool:
    text = "\n".join(str(part or "") for part in parts)
    return bool(SCRIPT_INTENT_RE.search(text))


def build_strategy_language_context(
    *,
    template: str | None = None,
    user_prompt: str | None = None,
    attached_context: str | None = None,
    max_chars: int = 5000,
) -> str:
    """Return compact context that teaches the LLM the app's Strategy Lab language constraints."""
    prompt = str(user_prompt or "")
    context = str(attached_context or "")
    template_text = str(template or "")

    # Always include the core constraints for Strategy AI. The block is small and
    # prevents expensive generic pandas/numpy answers.
    blocks = [CORE_STRATEGY_LANGUAGE_REFERENCE.strip()]

    if is_strategy_script_intent(template_text, prompt, context):
        blocks.append(
            """\
## Output mode for this request

The user appears to be asking about strategy code or backtest improvement.
Prioritize app-compatible Strategy Lab output. Do not invent a standalone pandas/numpy strategy_script().
If the user asked for code, return the revised Strategy Lab script only unless they requested explanation."""
        )

    value = "\n\n".join(block.strip() for block in blocks if block and block.strip()).strip()
    if len(value) > max_chars:
        return value[: max(0, max_chars - 80)].rstrip() + "\n\n[Strategy language reference truncated.]"
    return value


def detect_app_language_violations(text: str | None) -> list[StrategyLanguageViolation]:
    """Detect obvious generic-Python output that is not suitable for Strategy Lab scripts."""
    value = str(text or "")
    findings: list[StrategyLanguageViolation] = []
    for label, detail, pattern in VIOLATION_PATTERNS:
        if pattern.search(value):
            findings.append(StrategyLanguageViolation(label=label, detail=detail))
    return findings


def format_violation_summary(text: str | None) -> str:
    findings = detect_app_language_violations(text)
    if not findings:
        return ""
    lines = ["Potential Strategy Lab compatibility issue(s):"]
    for finding in findings:
        lines.append(f"- {finding.label}: {finding.detail}")
    return "\n".join(lines)
