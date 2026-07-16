from __future__ import annotations

from datetime import datetime
from typing import Any


MAX_FIELD_CHARS = 1200


def _clean_text(value: Any, *, limit: int = MAX_FIELD_CHARS) -> str:
    text = str(value or "").replace("\x00", "").strip()
    if len(text) > limit:
        return text[: max(0, limit - 20)].rstrip() + " ...[truncated]"
    return text


def _item_title(item: dict[str, Any]) -> str:
    title = _clean_text(item.get("title") or item.get("name") or item.get("series_id") or "Untitled", limit=180)
    source = _clean_text(item.get("source") or item.get("provider") or "Source", limit=80)
    return f"{source} - {title}"


def _item_url(item: dict[str, Any]) -> str:
    return _clean_text(item.get("url") or item.get("href") or item.get("link") or item.get("official_url") or "", limit=500)


def _item_summary(item: dict[str, Any]) -> str:
    parts: list[str] = []

    summary = _clean_text(item.get("summary") or item.get("description") or "", limit=700)
    if summary:
        parts.append(summary)

    series_id = _clean_text(item.get("series_id") or item.get("fred_series_id") or "", limit=80)
    if series_id:
        parts.append(f"Series ID: {series_id}")

    latest_date = _clean_text(item.get("latest_date") or item.get("date") or item.get("observation_date") or "", limit=80)
    latest_value = _clean_text(item.get("latest_value") or item.get("value") or "", limit=120)
    if latest_date or latest_value:
        parts.append(f"Latest observation: {latest_date or 'date unavailable'} = {latest_value or 'value unavailable'}")

    prior_value = _clean_text(item.get("prior_value") or "", limit=120)
    change_value = _clean_text(item.get("change") or item.get("delta") or item.get("change_value") or "", limit=120)
    if prior_value:
        parts.append(f"Prior value: {prior_value}")
    if change_value:
        parts.append(f"Change: {change_value}")

    units = _clean_text(item.get("units") or "", limit=120)
    frequency = _clean_text(item.get("frequency") or "", limit=120)
    if units or frequency:
        parts.append(f"Units/frequency: {units or 'units unavailable'}; {frequency or 'frequency unavailable'}")

    confidence = _clean_text(item.get("confidence") or item.get("quality") or item.get("status") or "", limit=80)
    if confidence:
        parts.append(f"Result status: {confidence}")

    return "; ".join(parts).strip()


def brief_to_strategy_ai_context(
    brief: list[dict[str, Any]] | None,
    *,
    max_items: int = 12,
    generated_at: datetime | None = None,
) -> str:
    """Convert a user-selected Newsroom brief into Strategy AI attached context.

    This is intentionally read-only context. It does not grant the AI browser,
    broker, file-system, or order-placement access.
    """
    items = list(brief or [])[: max(1, int(max_items or 12))]
    now = generated_at or datetime.now()

    lines: list[str] = [
        "## Attached Research Brief",
        "",
        f"Generated: {now.isoformat(timespec='seconds')}",
        f"Selected items: {len(items)}",
        "",
        "Safety/use notes:",
        "- This is user-selected research context only.",
        "- Treat source values as research inputs, not trading instructions.",
        "- Do not infer broker/account data from this brief.",
        "- Do not place, recommend automatic placement of, or simulate real broker orders from this context alone.",
        "",
    ]

    if not items:
        lines += ["No research brief items were selected."]
        return "\n".join(lines).strip() + "\n"

    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue

        lines.append(f"### {idx}. {_item_title(item)}")

        url = _item_url(item)
        if url:
            lines.append(f"- URL: {url}")

        item_id = _clean_text(item.get("id") or "", limit=160)
        if item_id:
            lines.append(f"- Item ID: {item_id}")

        source_type = _clean_text(item.get("kind") or item.get("type") or item.get("result_type") or "", limit=120)
        if source_type:
            lines.append(f"- Result type: {source_type}")

        summary = _item_summary(item)
        if summary:
            lines.append(f"- Summary: {summary}")

        note = _clean_text(item.get("note") or item.get("reason") or "", limit=300)
        if note:
            lines.append(f"- Note: {note}")

        lines.append("")

    lines += [
        "## Suggested AI handling",
        "",
        "Use the research brief together with any attached strategy/backtest context. "
        "Clearly separate source-backed facts from assumptions and keep the answer advisory-only.",
    ]

    return "\n".join(lines).strip() + "\n"


def default_newsroom_ai_prompt() -> str:
    return (
        "Use the attached Newsroom research brief as read-only context. "
        "Summarize the most relevant market or macro points for the current strategy. "
        "Keep the response concise and separate facts from assumptions."
    )


def brief_item_count(brief: list[dict[str, Any]] | None) -> int:
    return len(list(brief or []))
