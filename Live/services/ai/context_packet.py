from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyAIContextReport:
    has_research_brief: bool
    has_strategy_context: bool
    has_strategy_script: bool
    has_backtest_results: bool
    original_chars: int
    prepared_chars: int
    trimmed_chart_json: bool

    def as_lines(self) -> list[str]:
        return [
            "## Context Inventory",
            f"- Research brief attached: {'yes' if self.has_research_brief else 'no'}",
            f"- Strategy context attached: {'yes' if self.has_strategy_context else 'no'}",
            f"- Strategy script attached: {'yes' if self.has_strategy_script else 'no'}",
            f"- Backtest results attached: {'yes' if self.has_backtest_results else 'no'}",
            f"- Original context chars: {self.original_chars}",
            f"- Prepared context chars: {self.prepared_chars}",
            f"- Removed bulky chart JSON: {'yes' if self.trimmed_chart_json else 'no'}",
            "",
        ]


_STRATEGY_BLOCK_RE = re.compile(
    r"(?P<header>##\s+Strategy Script\s*)\n```(?P<script>.*?)```",
    re.IGNORECASE | re.DOTALL,
)

_RESEARCH_START_RE = re.compile(r"(^|\n)#\s*Research Brief\b", re.IGNORECASE)
_STRATEGY_CONTEXT_RE = re.compile(r"(^|\n)#\s*Current Strategy Context\b", re.IGNORECASE)
_BACKTEST_RE = re.compile(r"(^|\n)##\s*Current Backtest Results\b", re.IGNORECASE)


def _normalize_text(value: object) -> str:
    text = str(value or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.strip()


def _extract_strategy_script(text: str) -> str:
    match = _STRATEGY_BLOCK_RE.search(text or "")
    if not match:
        return ""

    script = str(match.group("script") or "").strip()
    if script.lower().startswith(("text\n", "python\n", "strategy\n")):
        script = script.split("\n", 1)[1].strip()
    return script


def _strip_cumulative_pnl_plotly_payload(text: str) -> tuple[str, bool]:
    original = text or ""
    patterns = [
        r"(?P<head>\nCumulative PnL\s*)\n\{.*?(?=\n## |\n# |\Z)",
        r"(?P<head>\nCumulative PnL\s*)\n\[.*?(?=\n## |\n# |\Z)",
    ]

    cleaned = original
    changed = False
    for pattern in patterns:
        cleaned_new, count = re.subn(
            pattern,
            r"\g<head>\n[chart JSON removed before sending to AI]",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if count:
            cleaned = cleaned_new
            changed = True

    return cleaned.strip(), changed


def _section_between(text: str, start_pattern: str, end_pattern: str | None = None) -> str:
    start = re.search(start_pattern, text or "", flags=re.IGNORECASE | re.DOTALL)
    if not start:
        return ""

    start_idx = start.start()
    if end_pattern:
        end = re.search(end_pattern, text[start.end():], flags=re.IGNORECASE | re.DOTALL)
        if end:
            return text[start_idx : start.end() + end.start()].strip()

    return text[start_idx:].strip()


def _compact_section(text: str, max_chars: int) -> str:
    text = _normalize_text(text)
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n[section truncated for AI context budget]"


def _make_language_rules() -> str:
    return "\n".join(
        [
            "## Strategy Lab Output Rules",
            "- The app strategy language is Pine-inspired, not unrestricted Python.",
            "- Use indicator assignments such as: fast = ta.ema(close, 9)",
            "- Use boolean conditions such as: longSignal = bullCross and close > trend",
            "- Use session filters such as: inSession = session(\"0930-1600\")",
            "- Use signals such as: buy when longSignal / sell when exitSignal",
            "- Use plots such as: plot fast",
            "- Do not use imports, pandas, numpy, classes, def, return, print, files, broker APIs, or external tools.",
            "- When the user asks to improve a script, return an app-compatible Strategy Lab script, not a Python function.",
            "",
        ]
    )


def _wants_strategy_script(prompt: str) -> bool:
    prompt_l = str(prompt or "").lower()
    return any(
        phrase in prompt_l
        for phrase in (
            "improve the current strategy",
            "improve this strategy",
            "improve the script",
            "return only",
            "script only",
            "revised strategy",
            "strategy script",
        )
    )


def prepare_strategy_ai_context(context: object, *, user_prompt: str = "", max_chars: int = 18000) -> tuple[str, StrategyAIContextReport]:
    original = _normalize_text(context)
    original_chars = len(original)

    trimmed, removed_chart_json = _strip_cumulative_pnl_plotly_payload(original)

    strategy_script = _extract_strategy_script(trimmed)
    has_research = bool(_RESEARCH_START_RE.search(trimmed))
    has_strategy_context = bool(_STRATEGY_CONTEXT_RE.search(trimmed))
    has_backtest = bool(_BACKTEST_RE.search(trimmed))

    research_section = ""
    current_context_section = ""

    if has_research:
        research_section = _section_between(
            trimmed,
            r"(^|\n)#\s*Research Brief\b",
            r"(^|\n)#\s*Current Strategy Context\b",
        )

    if has_strategy_context:
        current_context_section = _section_between(
            trimmed,
            r"(^|\n)#\s*Current Strategy Context\b",
            None,
        )

    generic_context = _STRATEGY_BLOCK_RE.sub(
        "## Strategy Script\n[script promoted to priority section below]",
        current_context_section or trimmed,
    ).strip()

    packet_parts: list[str] = [
        "# Strategy AI Prepared Context",
        "",
        _make_language_rules(),
    ]

    provisional_report = StrategyAIContextReport(
        has_research_brief=has_research,
        has_strategy_context=has_strategy_context,
        has_strategy_script=bool(strategy_script),
        has_backtest_results=has_backtest,
        original_chars=original_chars,
        prepared_chars=0,
        trimmed_chart_json=removed_chart_json,
    )
    packet_parts.extend(provisional_report.as_lines())

    if strategy_script:
        packet_parts.extend(
            [
                "## Priority Strategy Script",
                "The following is the current Strategy Lab script to edit when the user asks to improve the current strategy.",
                "```",
                strategy_script,
                "```",
                "",
            ]
        )
    elif _wants_strategy_script(user_prompt):
        packet_parts.extend(
            [
                "## Priority Strategy Script",
                "[missing]",
                "The user appears to be asking for a script edit, but no Strategy Script block was detected in attached context.",
                "",
            ]
        )

    if research_section:
        packet_parts.extend(
            [
                "## Research Brief",
                _compact_section(research_section, 4500),
                "",
            ]
        )

    if generic_context:
        packet_parts.extend(
            [
                "## Strategy / Backtest Context",
                _compact_section(generic_context, 9000),
                "",
            ]
        )

    prepared = "\n".join(part for part in packet_parts if part is not None).strip()

    if len(prepared) > max_chars:
        prepared = prepared[:max_chars].rstrip() + "\n[context packet truncated after preserving priority sections]"

    report = StrategyAIContextReport(
        has_research_brief=has_research,
        has_strategy_context=has_strategy_context,
        has_strategy_script=bool(strategy_script),
        has_backtest_results=has_backtest,
        original_chars=original_chars,
        prepared_chars=len(prepared),
        trimmed_chart_json=removed_chart_json,
    )

    old_inventory = "\n".join(provisional_report.as_lines()).strip()
    new_inventory = "\n".join(report.as_lines()).strip()
    if old_inventory in prepared:
        prepared = prepared.replace(old_inventory, new_inventory, 1)

    return prepared, report


def should_warn_missing_strategy_script(prompt: str, report: StrategyAIContextReport) -> bool:
    return _wants_strategy_script(prompt) and not bool(report.has_strategy_script)


def missing_strategy_script_message() -> str:
    return (
        "I need the current Strategy Lab script before I can return a script-only improvement. "
        "Attach Current Strategy Context, or paste the Strategy Script block into the attached context box."
    )
