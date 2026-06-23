from __future__ import annotations

import json
from typing import Any, Mapping

from .export_manager import sanitize_for_export


def _fmt(value: Any, default: str = "not available") -> str:
    if value is None or value == "":
        return default
    return str(sanitize_for_export(value))


def _json_block(value: Any) -> str:
    clean = sanitize_for_export(value)
    return "```json\n" + json.dumps(clean, indent=2, sort_keys=True, ensure_ascii=False) + "\n```"


def write_strategy_context_markdown(context: Mapping[str, Any]) -> str:
    clean = sanitize_for_export(dict(context))
    strategy_text = clean.get("strategy_text") or clean.get("strategy_code") or ""

    lines = [
        "# Strategy Context",
        "",
        f"- Symbol: {_fmt(clean.get('symbol'))}",
        f"- Timeframe: {_fmt(clean.get('timeframe'))}",
        f"- Start: {_fmt(clean.get('start'))}",
        f"- End: {_fmt(clean.get('end'))}",
        f"- Initial cash: {_fmt(clean.get('initial_cash'))}",
        f"- Quantity: {_fmt(clean.get('quantity'))}",
        "",
        "## Strategy Script",
        "",
        "```text",
        str(strategy_text).strip(),
        "```",
        "",
    ]

    if clean.get("validation_messages"):
        lines.extend(["## Validation Messages", "", _json_block(clean.get("validation_messages")), ""])

    if clean.get("backtest_summary"):
        lines.extend(["## Backtest Summary", "", _json_block(clean.get("backtest_summary")), ""])

    if clean.get("metadata"):
        lines.extend(["## Metadata", "", _json_block(clean.get("metadata")), ""])

    return "\n".join(lines).strip() + "\n"


def write_backtest_report_markdown(report: Mapping[str, Any]) -> str:
    clean = sanitize_for_export(dict(report))
    summary = clean.get("summary") or clean.get("backtest_summary") or {}

    lines = [
        "# Backtest Report",
        "",
        f"- Symbol: {_fmt(clean.get('symbol'))}",
        f"- Timeframe: {_fmt(clean.get('timeframe'))}",
        f"- Start: {_fmt(clean.get('start'))}",
        f"- End: {_fmt(clean.get('end'))}",
        "",
        "## Summary",
        "",
        _json_block(summary),
        "",
    ]

    if clean.get("strategy_text") or clean.get("strategy_code"):
        lines.extend([
            "## Strategy Script",
            "",
            "```text",
            str(clean.get("strategy_text") or clean.get("strategy_code") or "").strip(),
            "```",
            "",
        ])

    if clean.get("trades"):
        lines.extend(["## Trades", "", _json_block(clean.get("trades")), ""])

    if clean.get("equity_curve"):
        lines.extend(["## Equity Curve", "", "_Equity curve is available in the JSON export._", ""])

    if clean.get("metadata"):
        lines.extend(["## Metadata", "", _json_block(clean.get("metadata")), ""])

    return "\n".join(lines).strip() + "\n"


def write_research_brief_markdown(brief: Mapping[str, Any]) -> str:
    clean = sanitize_for_export(dict(brief))
    items = clean.get("items") or clean.get("sources") or []

    lines = [
        "# Research Brief",
        "",
        f"- Topic: {_fmt(clean.get('topic'))}",
        f"- Created at: {_fmt(clean.get('created_at'))}",
        "",
        "## Thesis / Question",
        "",
        _fmt(clean.get("question") or clean.get("prompt"), default="No question supplied."),
        "",
        "## Selected Sources",
        "",
    ]

    if not items:
        lines.append("_No source items selected._")
    else:
        for index, item in enumerate(items, start=1):
            if isinstance(item, Mapping):
                title = item.get("title") or item.get("name") or f"Source {index}"
                source = item.get("source") or item.get("publisher") or item.get("provider") or ""
                url = item.get("url") or item.get("link") or ""
                summary = item.get("summary") or item.get("description") or ""
                lines.extend([
                    f"### {index}. {_fmt(title)}",
                    "",
                    f"- Source: {_fmt(source)}",
                    f"- URL: {_fmt(url)}",
                    "",
                    _fmt(summary, default="No summary supplied."),
                    "",
                ])
            else:
                lines.extend([f"### {index}. Source Item", "", _fmt(item), ""])

    if clean.get("notes"):
        lines.extend(["## Notes", "", _fmt(clean.get("notes")), ""])

    return "\n".join(lines).strip() + "\n"
