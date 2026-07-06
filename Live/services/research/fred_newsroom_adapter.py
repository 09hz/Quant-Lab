from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, List, Optional


def _source_selected(sources: Optional[Iterable[str]], source_id: str) -> bool:
    if sources is None:
        return True
    normalized = {str(item or "").strip().lower().replace("-", "_") for item in sources}
    aliases = {
        source_id,
        source_id.replace("_", "-"),
    }
    if source_id == "fred":
        aliases.update({"federal_reserve_economic_data", "stlouisfed", "st_louis_fed"})
    return bool(normalized.intersection(aliases))


def _format_number(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):,.6g}"
    except Exception:
        return str(value)


def _format_change(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        number = float(value)
        sign = "+" if number > 0 else ""
        return f"{sign}{number:,.6g}"
    except Exception:
        return str(value)


def _series_summary_to_item(summary: dict[str, Any], *, topic: str, index: int) -> dict[str, Any]:
    series_id = str(summary.get("series_id") or f"series-{index}").upper().strip()
    title = str(summary.get("title") or series_id)
    latest_value = summary.get("latest_value")
    latest_date = summary.get("latest_date")
    previous_value = summary.get("previous_value")
    previous_date = summary.get("previous_date")
    change = summary.get("change")
    units = str(summary.get("units") or "units n/a")
    frequency = str(summary.get("frequency") or "frequency n/a")
    error = str(summary.get("error") or "").strip()

    if error:
        summary_text = (
            f"FRED structured fetch attempted for {series_id}, but the connector returned an error: {error}. "
            "Open the official FRED page to review the series manually."
        )
        confidence = "medium"
        selectable = False
        kind = "fred-data-warning"
    else:
        summary_text = (
            f"Latest FRED value for {series_id}: {_format_number(latest_value)} on {latest_date or 'n/a'} "
            f"({units}, {frequency}). Prior value: {_format_number(previous_value)} on {previous_date or 'n/a'}; "
            f"change vs prior: {_format_change(change)}."
        )
        confidence = "high"
        selectable = True
        kind = "fred-data"

    return {
        "id": f"fred-data-{index}-{series_id.lower()}",
        "title": f"{series_id}: {title}",
        "source": "FRED",
        "url": summary.get("source_url") or f"https://fred.stlouisfed.org/series/{series_id}",
        "summary": summary_text,
        "topic": topic,
        "kind": kind,
        "confidence": confidence,
        "needs_manual_search": False,
        "selectable": selectable,
        "metadata": {
            "connector": "fred",
            "series_id": series_id,
            "title": title,
            "units": units,
            "frequency": frequency,
            "latest_date": latest_date,
            "latest_value": latest_value,
            "previous_date": previous_date,
            "previous_value": previous_value,
            "change": change,
            "observation_count": summary.get("observation_count"),
            "fetched_at": summary.get("fetched_at"),
            "error": error or None,
        },
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    }


def _candidate_to_item(candidate: dict[str, Any], *, topic: str, index: int, warning: str = "") -> dict[str, Any]:
    series_id = str(candidate.get("series_id") or f"candidate-{index}").upper().strip()
    title = str(candidate.get("title") or series_id)
    reason = str(candidate.get("reason") or "curated FRED macro series")
    warning_text = f" {warning}" if warning else ""
    return {
        "id": f"fred-link-{index}-{series_id.lower()}",
        "title": f"{series_id}: {title}",
        "source": "FRED",
        "url": candidate.get("source_url") or f"https://fred.stlouisfed.org/series/{series_id}",
        "summary": f"Curated FRED candidate for this query: {reason}.{warning_text}",
        "topic": topic,
        "kind": "fred-series-link",
        "confidence": candidate.get("relevance") or "medium",
        "needs_manual_search": False,
        "selectable": True,
        "metadata": {
            "connector": "fred",
            "series_id": series_id,
            "topic": candidate.get("topic"),
            "reason": reason,
            "api_configured": False,
        },
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    }


def build_fred_newsroom_items(
    topic: str,
    *,
    max_series: int = 4,
    observation_limit: int = 24,
    timeout_seconds: float | None = None,
) -> list[dict[str, Any]]:
    """Build Newsroom result items from the FRED connector.

    The returned items are safe to place in the selectable research brief. They
    contain compact structured values only; the AI does not receive direct API
    access.
    """

    topic_clean = " ".join(str(topic or "").split()) or "market conditions"

    try:
        from services.research.fred_connector import build_fred_research_brief
    except Exception as exc:
        return [
            {
                "id": "fred-connector-unavailable",
                "title": "FRED connector unavailable",
                "source": "FRED",
                "url": "https://fred.stlouisfed.org/",
                "summary": f"FRED connector could not be imported: {exc}",
                "topic": topic_clean,
                "kind": "fred-data-warning",
                "confidence": "low",
                "needs_manual_search": True,
                "selectable": False,
                "metadata": {"connector": "fred", "error": str(exc)},
                "fetched_at": datetime.now().isoformat(timespec="seconds"),
            }
        ]

    try:
        brief = build_fred_research_brief(
            topic_clean,
            max_series=max_series,
            observation_limit=observation_limit,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:
        return [
            {
                "id": "fred-brief-error",
                "title": "FRED data fetch failed",
                "source": "FRED",
                "url": "https://fred.stlouisfed.org/",
                "summary": f"FRED data fetch failed: {exc}",
                "topic": topic_clean,
                "kind": "fred-data-warning",
                "confidence": "low",
                "needs_manual_search": True,
                "selectable": False,
                "metadata": {"connector": "fred", "error": str(exc)},
                "fetched_at": datetime.now().isoformat(timespec="seconds"),
            }
        ]

    items: list[dict[str, Any]] = []
    summaries = list(brief.get("series_summaries") or [])
    for idx, summary in enumerate(summaries, start=1):
        items.append(_series_summary_to_item(dict(summary or {}), topic=topic_clean, index=idx))

    if not items:
        warnings = list(brief.get("warnings") or [])
        warning = warnings[0] if warnings else ""
        for idx, candidate in enumerate(list(brief.get("candidates") or [])[:max_series], start=1):
            items.append(_candidate_to_item(dict(candidate or {}), topic=topic_clean, index=idx, warning=warning))

    return items


def extend_results_with_fred(
    topic: str,
    sources: Optional[Iterable[str]],
    existing_results: list[dict[str, Any]] | None,
    *,
    max_series: int = 4,
    observation_limit: int = 24,
) -> list[dict[str, Any]]:
    """Prepend structured FRED result items when FRED is selected."""

    results = list(existing_results or [])
    if not _source_selected(sources, "fred"):
        return results

    fred_items = build_fred_newsroom_items(
        topic,
        max_series=max_series,
        observation_limit=observation_limit,
    )

    if not fred_items:
        return results

    existing_ids = {str(item.get("id")) for item in results}
    unique_fred_items: list[dict[str, Any]] = []
    for item in fred_items:
        item_id = str(item.get("id") or "")
        if item_id in existing_ids:
            continue
        existing_ids.add(item_id)
        unique_fred_items.append(item)

    return unique_fred_items + results
