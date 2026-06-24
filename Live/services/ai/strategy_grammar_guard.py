"""
Strategy Lab grammar guard for AI Advisor prompts and responses.

This module intentionally stays lightweight and dependency-free. It does not
execute strategy code. It only gives the LLM a stricter contract and provides
simple validation helpers for generated Strategy Lab scripts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


STRICT_STRATEGY_LAB_GRAMMAR = """
# Strategy Lab Parser Contract

When editing or creating Strategy Lab scripts, use ONLY the app-supported
Strategy Lab syntax.

Allowed examples:
fast = ta.ema(close, 9)
slow = ta.ema(close, 21)
trend = ta.ema(close, 50)
r = ta.rsi(close, 14)
atr = ta.atr(close, 14)
atrSma = ta.sma(atr, 14)

bullCross = ta.crossover(fast, slow)
bearCross = ta.crossunder(fast, slow)

inSession = session("0930-1600")
aboveTrend = close > trend
belowTrend = close < trend
rsiLowOk = r > 40
rsiHighOk = r < 65
volAbsOk = atr > 0.1
volTrendOk = atr > atrSma

longSignal = inSession and bullCross and aboveTrend and rsiLowOk and rsiHighOk and volAbsOk and volTrendOk
exitSignal = bearCross or belowTrend

plot fast
plot slow
plot trend

buy when longSignal
sell when exitSignal

Hard rules:
- Return Strategy Lab script syntax, not generic Python.
- Do not use imports.
- Do not use pandas or numpy.
- Do not define functions or classes.
- Do not use def strategy_script().
- Do not use >= or <=. Use separate simple variables with > and <.
- Do not put math inside boolean comparisons, e.g. do not write atr > atrSma * 0.8.
- Do not use inline multiplication/division/addition/subtraction inside condition assignments.
- Break complex logic into simple boolean variables.
- Use buy when <condition> for long entry.
- Use sell when <condition> for long exit.
- Do not create short-entry logic unless the user explicitly says the engine supports shorts.
- Do not use sell when shortSetup / buy when exitShort by default.
- For "script only" requests, return only the script. No markdown fence, no explanation, no comments.
""".strip()


@dataclass(frozen=True)
class GrammarIssue:
    line_number: int
    line: str
    code: str
    message: str


def build_strategy_grammar_reference() -> str:
    """Return the strict grammar reference inserted into every Strategy AI call."""
    return STRICT_STRATEGY_LAB_GRAMMAR


def augment_strategy_ai_prompt(prompt: str) -> str:
    """Append strict output instructions to the user's prompt."""
    clean = str(prompt or "").strip()
    guard = (
        "Use the Strategy Lab Parser Contract from the attached context. "
        "If asked to improve or rewrite a strategy, return parser-compatible "
        "Strategy Lab script only: no imports, no pandas/numpy, no functions, "
        "no >= or <=, no inline math inside boolean comparisons, and no short "
        "logic unless explicitly requested and supported."
    )
    if not clean:
        return guard
    if "Strategy Lab Parser Contract" in clean:
        return clean
    return f"{clean}\n\n{guard}"


def strip_markdown_code_fences(text: str) -> str:
    """Remove a single surrounding markdown code fence if present."""
    raw = str(text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


def _has_inline_math_after_comparison(expr: str) -> bool:
    """Detect expressions such as atr > atrSma * 0.8 or close < trend + atr."""
    return bool(re.search(r"(?:>|<)\s*[^#\n]*(?:\*|/|\+|-)", expr))


def _is_comment_or_blank(line: str) -> bool:
    stripped = line.strip()
    return not stripped or stripped.startswith("#")


def validate_strategy_lab_script(text: str) -> list[GrammarIssue]:
    """Return parser-compatibility warnings for an AI-generated Strategy Lab script."""
    script = strip_markdown_code_fences(text)
    issues: list[GrammarIssue] = []

    for idx, raw_line in enumerate(script.splitlines(), start=1):
        line = raw_line.strip()
        if _is_comment_or_blank(line):
            continue

        lower = line.lower()

        def add(code: str, message: str) -> None:
            issues.append(GrammarIssue(idx, raw_line.rstrip(), code, message))

        if lower.startswith("import ") or lower.startswith("from "):
            add("python-import", "Do not use Python imports in Strategy Lab scripts.")

        if re.match(r"^(async\s+def|def|class)\b", lower):
            add("python-definition", "Do not define Python functions/classes in Strategy Lab scripts.")

        if "pandas" in lower or "numpy" in lower or re.search(r"\b(pd|np)\.", line):
            add("python-library", "Do not use pandas/numpy objects in Strategy Lab scripts.")

        if ">=" in line or "<=" in line:
            add("unsupported-comparator", "Use parser-friendly > and < comparisons instead of >= or <=.")

        if "=" in line and not line.lower().startswith(("buy when", "sell when", "plot ")):
            _lhs, rhs = line.split("=", 1)
            rhs = rhs.strip()

            if (" and " in rhs or " or " in rhs) and _has_inline_math_after_comparison(rhs):
                add(
                    "inline-math-condition",
                    "Do not place math inside boolean comparisons. Split it into simple variables first.",
                )

            if re.search(r"(?:>|<)\s*[\w.]+\s*(?:\*|/|\+|-)", rhs):
                add(
                    "comparison-expression",
                    "Comparison right-hand side should be a simple variable or number, not an arithmetic expression.",
                )

        if re.match(r"^sell\s+when\s+short", lower):
            add("short-entry-sell", "Do not use sell when shortSetup unless short entries are explicitly supported.")

        if re.match(r"^buy\s+when\s+exitshort", lower):
            add("short-exit-buy", "Do not use buy when exitShort unless short entries are explicitly supported.")

        if re.search(r"\bshortsetup\b|\bexitshort\b", lower):
            add("short-logic", "Short strategy variables are risky unless the engine supports true shorts.")

    return issues


def format_grammar_issues(issues: Iterable[GrammarIssue]) -> str:
    """Format issues for CLI/debug display."""
    items = list(issues)
    if not items:
        return "No Strategy Lab grammar issues detected."

    lines = ["Strategy Lab grammar issues detected:"]
    for item in items:
        lines.append(f"- Line {item.line_number}: {item.code}: {item.message}")
        lines.append(f"  {item.line}")
    return "\n".join(lines)


def summarize_grammar_issues(text: str, *, max_items: int = 5) -> str:
    """Short summary for status panels or logs."""
    issues = validate_strategy_lab_script(text)
    if not issues:
        return "Strategy Lab grammar check passed."
    shown = issues[: max(1, int(max_items))]
    parts = [f"L{i.line_number}:{i.code}" for i in shown]
    suffix = "" if len(issues) <= len(shown) else f" +{len(issues) - len(shown)} more"
    return "Strategy Lab grammar warning: " + ", ".join(parts) + suffix
