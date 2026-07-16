from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

from services.research.research_analyst_scope import plan_research_scope


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _clean_text(value: Any, *, max_len: int = 900) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) > max_len:
        return text[: max_len - 1].rstrip() + "..."
    return text


def _to_float(value: Any) -> float | None:
    try:
        text = str(value).strip()
        if not text or text == ".":
            return None
        return float(text)
    except Exception:
        return None


def _fred_api_key() -> str:
    for key in ("FRED_API_KEY", "FRED_API_KEY_ID"):
        value = os.getenv(key)
        if value:
            return str(value).strip()
    return ""


def _fetch_fred_observations(series_id: str, *, limit: int = 6, api_key: str = "") -> list[dict[str, Any]]:
    key = api_key or _fred_api_key()
    if not key:
        return []

    params = {
        "series_id": series_id,
        "api_key": key,
        "file_type": "json",
        "sort_order": "desc",
        "limit": str(max(2, min(12, int(limit or 6)))),
    }
    url = "https://api.stlouisfed.org/fred/series/observations?" + urlencode(params)
    with urlopen(url, timeout=12) as response:  # nosec B310 - approved FRED API endpoint only
        payload = json.loads(response.read().decode("utf-8"))

    observations = payload.get("observations") or []
    out: list[dict[str, Any]] = []
    for row in observations:
        if not isinstance(row, dict):
            continue
        value = _to_float(row.get("value"))
        if value is None:
            continue
        out.append({"date": row.get("date", ""), "value": value})
    return out


def _series_item_from_observations(series: dict[str, Any], observations: list[dict[str, Any]]) -> dict[str, Any]:
    series_id = str(series.get("series_id") or "").strip()
    label = str(series.get("label") or series_id).strip()
    category = str(series.get("category") or "macro").strip()
    role = str(series.get("evidence_role") or "macro context").strip()
    url = str(series.get("url") or f"https://fred.stlouisfed.org/series/{series_id}").strip()

    latest = observations[0] if observations else {}
    previous = observations[1] if len(observations) > 1 else {}
    latest_value = latest.get("value")
    previous_value = previous.get("value")

    change_text = "not available"
    if isinstance(latest_value, (int, float)) and isinstance(previous_value, (int, float)):
        change = latest_value - previous_value
        change_text = f"{change:+.4g} vs prior observation"

    if observations:
        summary = (
            f"Structured FRED observation for {series_id} ({label}). "
            f"Latest available observation: {latest.get('date', '')} = {latest_value}. "
            f"Prior observation: {previous.get('date', '')} = {previous_value}. "
            f"Change: {change_text}. Evidence role: {role}. "
            "Use as confirmed FRED series data, but label market/sector conclusions as interpretation or proxy-only when appropriate."
        )
        confidence = "high"
        validity = "high"
    else:
        summary = (
            f"FRED structured observation for {series_id} ({label}) could not be loaded. "
            "This is a source-discovery item only; do not treat it as a confirmed data point."
        )
        confidence = "low"
        validity = "source-discovery"

    return {
        "id": f"fred-structured-{series_id}",
        "title": f"FRED structured data: {series_id} - {label}",
        "source": "FRED",
        "url": url,
        "summary": summary,
        "topic": category,
        "kind": "fred-structured-observation" if observations else "fred-source-discovery",
        "confidence": confidence,
        "validity": validity,
        "relevance": "high",
        "source_type": "official",
        "source_role": "structured-gap-fill" if observations else "source-discovery",
        "used_for_ai": True,
        "selectable": True,
        "published_at": str(latest.get("date", "")),
        "metadata": {
            "connector": "fred",
            "series_id": series_id,
            "series_label": label,
            "category": category,
            "evidence_role": role,
            "latest_observation": latest,
            "previous_observation": previous,
            "observation_count": len(observations),
            "generated_at": _now_iso(),
        },
    }


def build_structured_gap_fill_items(
    *,
    question: str = "",
    topic: str = "",
    symbol: str = "",
    selected_sources: list[str] | tuple[str, ...] | None = None,
    max_items: int = 18,
    fetch_live: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any], str | None]:
    """
    Build structured official-data items for Research Analyst answers.

    This is deliberately limited to approved official source connectors. It does
    not give the LLM unrestricted browsing. Search landing pages remain
    source-discovery context only.
    """
    selected = {str(item).lower() for item in (selected_sources or [])}
    fred_allowed = not selected or "fred" in selected
    plan = plan_research_scope(question=question, topic=topic, symbol=symbol, max_series=max_items)

    if not fred_allowed:
        return [], plan, "FRED was not selected in the Newsroom source filter, so structured FRED gap-fill was skipped."

    api_key = _fred_api_key()
    items: list[dict[str, Any]] = []
    errors: list[str] = []

    for series in plan.get("series", [])[:max_items]:
        series_id = str(series.get("series_id") or "").strip()
        observations: list[dict[str, Any]] = []
        if fetch_live and api_key and series_id:
            try:
                observations = _fetch_fred_observations(series_id, api_key=api_key)
            except Exception as exc:
                errors.append(f"{series_id}: {exc}")
        items.append(_series_item_from_observations(series, observations))

    if not api_key:
        errors.append("FRED_API_KEY is not available; structured gap-fill returned source-discovery cards only.")

    return items, plan, "; ".join(errors) if errors else None


build_research_analyst_gap_fill_items = build_structured_gap_fill_items
