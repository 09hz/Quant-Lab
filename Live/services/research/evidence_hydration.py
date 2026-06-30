from __future__ import annotations

from datetime import datetime, timezone
import csv
import io
import re
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen


FRED_GRAPH_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"

_SERIES_RE = re.compile(r"/series/([A-Za-z0-9_]+)")
_TITLE_RE = re.compile(r"\bFRED\s+([A-Za-z][A-Za-z0-9_]{1,24})\b")


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _float_or_none(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text or text == ".":
        return None
    try:
        return float(text)
    except Exception:
        return None


def _round(value: float | None) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 6)
    except Exception:
        return None


def extract_fred_series_id(item: dict[str, Any] | None) -> str:
    if not isinstance(item, dict):
        return ""

    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        series_id = _clean(metadata.get("series_id")).upper()
        if series_id:
            return series_id

    for key in ("series_id", "fred_series_id"):
        series_id = _clean(item.get(key)).upper()
        if series_id:
            return series_id

    url = _clean(item.get("url") or item.get("source_url"))
    match = _SERIES_RE.search(url)
    if match:
        return match.group(1).upper()

    for key in ("id", "rec_id", "title", "summary"):
        text = _clean(item.get(key))
        match = _TITLE_RE.search(text)
        if match:
            return match.group(1).upper()

    return ""


def is_fred_recommendation(item: dict[str, Any] | None) -> bool:
    if not isinstance(item, dict):
        return False
    source = _clean(item.get("source")).lower()
    kind = _clean(item.get("kind")).lower()
    url = _clean(item.get("url")).lower()
    return (
        source == "fred"
        or "fred" in kind
        or "fred.stlouisfed.org/series/" in url
    ) and bool(extract_fred_series_id(item))


def _fetch_fred_csv_observations(series_id: str, *, timeout_seconds: float = 10.0) -> list[dict[str, Any]]:
    series_id = _clean(series_id).upper()
    if not series_id:
        raise ValueError("Missing FRED series id.")

    url = FRED_GRAPH_CSV_URL.format(series_id=quote(series_id, safe=""))
    request = Request(
        url,
        headers={
            "User-Agent": "AlgoTrader-Newsroom/1.0 (+local research tool)",
            "Accept": "text/csv,*/*",
        },
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        payload = response.read().decode("utf-8", errors="replace")

    rows: list[dict[str, Any]] = []
    reader = csv.DictReader(io.StringIO(payload))
    for row in reader:
        date = _clean(row.get("observation_date") or row.get("DATE") or row.get("date"))
        raw_value = row.get(series_id)
        if raw_value is None:
            for key, value in row.items():
                if key and key.lower() not in {"observation_date", "date"}:
                    raw_value = value
                    break
        value = _float_or_none(raw_value)
        if date and value is not None:
            rows.append({"date": date, "value": value})

    if not rows:
        raise RuntimeError(f"No numeric FRED observations returned for {series_id}.")
    return rows


def _trend_from_ascending_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = [row for row in rows if _float_or_none(row.get("value")) is not None]
    if not values:
        return {
            "latest_date": "",
            "latest": None,
            "prior_date": "",
            "prior": None,
            "change_1": None,
            "change_3": None,
            "change_6": None,
            "direction_1": "unknown",
            "direction_3": "unknown",
            "direction_6": "unknown",
            "observations_used": 0,
        }

    latest = values[-1]
    latest_value = _float_or_none(latest.get("value"))

    def older(back: int) -> dict[str, Any]:
        if len(values) <= back:
            return {}
        return values[-1 - back]

    prior = older(1)
    prior_value = _float_or_none(prior.get("value"))

    def delta(back: int) -> float | None:
        old = older(back)
        old_value = _float_or_none(old.get("value"))
        if latest_value is None or old_value is None:
            return None
        return latest_value - old_value

    def direction(value: float | None) -> str:
        if value is None:
            return "unknown"
        if value > 0:
            return "rising"
        if value < 0:
            return "falling"
        return "flat"

    change_1 = _round(delta(1))
    change_3 = _round(delta(3))
    change_6 = _round(delta(6))

    return {
        "latest_date": _clean(latest.get("date")),
        "latest": _round(latest_value),
        "prior_date": _clean(prior.get("date")),
        "prior": _round(prior_value),
        "change_1": change_1,
        "change_3": change_3,
        "change_6": change_6,
        "direction_1": direction(change_1),
        "direction_3": direction(change_3),
        "direction_6": direction(change_6),
        "observations_used": len(values),
    }


def _trend_summary(series_id: str, title: str, trend: dict[str, Any]) -> str:
    latest = trend.get("latest")
    latest_date = trend.get("latest_date") or "unknown date"
    prior = trend.get("prior")
    prior_date = trend.get("prior_date") or "prior observation"
    parts = [
        f"{series_id} hydrated official FRED observation: latest value {latest} on {latest_date}."
    ]
    if prior is not None:
        parts.append(
            f"Prior value {prior} on {prior_date}; 1-period change {trend.get('change_1')} ({trend.get('direction_1')})."
        )
    if trend.get("change_3") is not None:
        parts.append(f"3-period change {trend.get('change_3')} ({trend.get('direction_3')}).")
    if trend.get("change_6") is not None:
        parts.append(f"6-period change {trend.get('change_6')} ({trend.get('direction_6')}).")
    parts.append("Treat this as confirmed official FRED data for evidence audit and quant filters.")
    return " ".join(parts)


def build_hydrated_fred_evidence_item(
    recommendation: dict[str, Any],
    *,
    observations: list[dict[str, Any]],
    added_at: str | None = None,
    sequence: int | None = None,
) -> dict[str, Any]:
    series_id = extract_fred_series_id(recommendation)
    if not series_id:
        raise ValueError("Could not extract FRED series id from recommendation.")

    title = _clean(recommendation.get("title"))
    title = re.sub(r"^FRED\s+", "", title, flags=re.IGNORECASE).strip(" -") or series_id
    trend = _trend_from_ascending_rows(observations)
    fetched_at = _now_iso()
    metadata = dict(recommendation.get("metadata") or {})
    metadata.update(
        {
            "connector": "fred-public-csv",
            "series_id": series_id,
            "trend": trend,
            "hydrated": True,
            "hydrated_at": fetched_at,
            "approved_from_queue": True,
            "approved_at": added_at or fetched_at,
            "recommendation_id": recommendation.get("id") or recommendation.get("rec_id"),
            "recommendation_bucket": recommendation.get("bucket"),
        }
    )

    item = {
        "id": f"hydrated-fred-{series_id}-{(added_at or fetched_at).replace(':', '').replace('-', '')}",
        "title": f"FRED hydrated official data: {series_id} - {title}",
        "source": "FRED",
        "url": f"https://fred.stlouisfed.org/series/{series_id}",
        "summary": _trend_summary(series_id, title, trend),
        "topic": f"Approved recommendation hydration: {recommendation.get('bucket') or 'macro'}",
        "kind": "fred-hydrated-official-data",
        "confidence": "high",
        "validity": "high",
        "relevance": "high",
        "source_type": "official",
        "source_role": "approved-hydrated-fred-evidence",
        "evidence_role": "approved-hydrated-fred-evidence",
        "approved_recommendation": True,
        "brief_user_approved_recommendation": True,
        "brief_added_at": added_at or fetched_at,
        "brief_added_sequence": sequence,
        "published_at": trend.get("latest_date") or "",
        "visible": True,
        "selectable": True,
        "user_addable": True,
        "used_for_ai": True,
        "metadata": metadata,
        "fetched_at": fetched_at,
    }
    return item


def _approval_discovery_item(
    recommendation: dict[str, Any],
    *,
    added_at: str | None,
    sequence: int | None,
    hydration_status: str,
    hydration_error: str = "",
) -> dict[str, Any]:
    item = dict(recommendation)
    metadata = dict(item.get("metadata") or {})
    metadata.update(
        {
            "approved_at": added_at or _now_iso(),
            "approved_from_queue": True,
            "hydration_status": hydration_status,
        }
    )
    if hydration_error:
        metadata["hydration_error"] = hydration_error

    item["metadata"] = metadata
    item["brief_user_approved_recommendation"] = True
    item["brief_added_at"] = added_at or _now_iso()
    item["brief_added_sequence"] = sequence
    item["approved_recommendation"] = True
    item["source_role"] = "approved-recommendation-discovery"
    item["evidence_role"] = "approved-recommendation-discovery"
    item["used_for_ai"] = True

    if hydration_error:
        original_summary = _clean(item.get("summary"))
        item["summary"] = (
            f"{original_summary} Hydration status: {hydration_status}. "
            f"Hydration warning: {hydration_error}. This remains discovery/context only until hydrated."
        ).strip()
    return item


def hydrate_approved_recommendation(
    recommendation: dict[str, Any],
    *,
    added_at: str | None = None,
    sequence: int | None = None,
    allow_network: bool = True,
    timeout_seconds: float = 10.0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(recommendation, dict):
        item = _approval_discovery_item(
            {},
            added_at=added_at,
            sequence=sequence,
            hydration_status="invalid-recommendation",
            hydration_error="Recommendation was not a dictionary.",
        )
        return item, {"hydrated": False, "discovery_only": True, "error": "invalid recommendation"}

    if not is_fred_recommendation(recommendation):
        item = _approval_discovery_item(
            recommendation,
            added_at=added_at,
            sequence=sequence,
            hydration_status="discovery-only",
        )
        return item, {"hydrated": False, "discovery_only": True, "series_id": ""}

    series_id = extract_fred_series_id(recommendation)
    if not allow_network:
        item = _approval_discovery_item(
            recommendation,
            added_at=added_at,
            sequence=sequence,
            hydration_status="network-disabled",
            hydration_error=f"Network fetch disabled for checker; series {series_id} was not hydrated.",
        )
        return item, {"hydrated": False, "discovery_only": True, "series_id": series_id, "error": "network disabled"}

    try:
        observations = _fetch_fred_csv_observations(series_id, timeout_seconds=timeout_seconds)
        item = build_hydrated_fred_evidence_item(
            recommendation,
            observations=observations,
            added_at=added_at,
            sequence=sequence,
        )
        return item, {"hydrated": True, "discovery_only": False, "series_id": series_id, "error": ""}
    except Exception as exc:
        item = _approval_discovery_item(
            recommendation,
            added_at=added_at,
            sequence=sequence,
            hydration_status="failed",
            hydration_error=str(exc),
        )
        return item, {"hydrated": False, "discovery_only": True, "series_id": series_id, "error": str(exc)}
