from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

import requests


BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
BLS_API_KEY = os.getenv("BLS_API_KEY", "").strip()

BLS_SERIES: dict[str, dict[str, str]] = {
    "CUSR0000SA0": {
        "title": "Consumer Price Index for All Urban Consumers: All Items in U.S. City Average",
        "category": "inflation",
        "unit": "Index 1982-1984=100",
        "frequency": "Monthly",
    },
    "CUSR0000SA0L1E": {
        "title": "Consumer Price Index for All Urban Consumers: All Items Less Food and Energy",
        "category": "inflation",
        "unit": "Index 1982-1984=100",
        "frequency": "Monthly",
    },
    "WPUFD4": {
        "title": "Producer Price Index by Commodity: Final Demand",
        "category": "producer_prices",
        "unit": "Index",
        "frequency": "Monthly",
    },
    "LNS14000000": {
        "title": "Unemployment Rate",
        "category": "labor",
        "unit": "Percent",
        "frequency": "Monthly",
    },
    "CES0000000001": {
        "title": "All Employees, Total Nonfarm",
        "category": "labor",
        "unit": "Thousands of persons",
        "frequency": "Monthly",
    },
    "CES0500000003": {
        "title": "Average Hourly Earnings of All Employees, Total Private",
        "category": "wages",
        "unit": "Dollars per hour",
        "frequency": "Monthly",
    },
}


def _source_selected(sources: Optional[Iterable[str]], source_id: str) -> bool:
    if sources is None:
        return True
    return source_id.lower() in {str(s).lower() for s in sources}


def _topic_mentions_bls(topic: str) -> bool:
    text = str(topic or "").lower()
    tokens = [
        "bls",
        "labor",
        "employment",
        "unemployment",
        "jobs",
        "payroll",
        "wage",
        "wages",
        "cpi",
        "ppi",
        "inflation",
        "producer price",
        "consumer price",
    ]
    return any(token in text for token in tokens)


def _series_for_topic(topic: str) -> list[str]:
    text = str(topic or "").lower()
    chosen: list[str] = []

    if any(token in text for token in ["cpi", "consumer price", "inflation"]):
        chosen.extend(["CUSR0000SA0", "CUSR0000SA0L1E"])
    if any(token in text for token in ["ppi", "producer price", "input cost"]):
        chosen.append("WPUFD4")
    if any(token in text for token in ["unemployment", "labor", "jobs", "employment"]):
        chosen.extend(["LNS14000000", "CES0000000001"])
    if any(token in text for token in ["wage", "wages", "earnings", "hourly"]):
        chosen.append("CES0500000003")

    if not chosen:
        chosen = [
            "CUSR0000SA0",
            "CUSR0000SA0L1E",
            "WPUFD4",
            "LNS14000000",
            "CES0000000001",
            "CES0500000003",
        ]

    seen: set[str] = set()
    output: list[str] = []
    for sid in chosen:
        sid = sid.upper()
        if sid in BLS_SERIES and sid not in seen:
            seen.add(sid)
            output.append(sid)
    return output


def _period_rank(period: str) -> int:
    period = str(period or "").upper()
    if re.match(r"^M\d{2}$", period):
        return int(period[1:])
    if re.match(r"^Q\d$", period):
        return int(period[1:]) * 3
    if re.match(r"^S\d$", period):
        return int(period[1:]) * 6
    if period == "A01":
        return 13
    return 0


def _period_label(year: str, period: str, period_name: str = "") -> str:
    period = str(period or "")
    year = str(year or "")
    if re.match(r"^M\d{2}$", period):
        month = int(period[1:])
        if 1 <= month <= 12:
            return f"{year}-{month:02d}-01"
    if re.match(r"^Q\d$", period):
        return f"{year} {period}"
    if period == "A01":
        return f"{year} annual"
    return " ".join(x for x in [year, period_name or period] if x)


def _as_float(value: Any) -> float | None:
    try:
        return float(str(value).replace(",", ""))
    except Exception:
        return None


def _format_number(value: Any) -> str:
    num = _as_float(value)
    if num is None:
        return str(value or "n/a")
    if abs(num) >= 1000:
        return f"{num:,.3f}".rstrip("0").rstrip(".")
    return f"{num:.3f}".rstrip("0").rstrip(".")


def _format_change(value: Any) -> str:
    num = _as_float(value)
    if num is None:
        return "n/a"
    sign = "+" if num >= 0 else ""
    return f"{sign}{num:.3f}".rstrip("0").rstrip(".")


def _fetch_bls_series(series_ids: list[str]) -> dict[str, Any]:
    current_year = datetime.now(timezone.utc).year
    payload: dict[str, Any] = {
        "seriesid": series_ids,
        "startyear": str(current_year - 2),
        "endyear": str(current_year),
    }
    if BLS_API_KEY:
        payload["registrationkey"] = BLS_API_KEY

    response = requests.post(
        BLS_API_URL,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _series_item(series: dict[str, Any], *, topic: str, index: int) -> dict[str, Any]:
    series_id = str(series.get("seriesID") or f"series-{index}").upper().strip()
    info = BLS_SERIES.get(series_id, {})
    data = series.get("data") or []
    if not isinstance(data, list):
        data = []

    usable = [
        row
        for row in data
        if isinstance(row, dict)
        and str(row.get("period") or "").upper() != "M13"
        and row.get("value") not in (None, "")
    ]
    usable.sort(
        key=lambda r: (
            int(str(r.get("year") or "0")),
            _period_rank(str(r.get("period") or "")),
        ),
        reverse=True,
    )

    latest = usable[0] if usable else {}
    previous = usable[1] if len(usable) > 1 else {}

    latest_value = latest.get("value")
    previous_value = previous.get("value")
    latest_date = _period_label(str(latest.get("year") or ""), str(latest.get("period") or ""), str(latest.get("periodName") or ""))
    previous_date = _period_label(str(previous.get("year") or ""), str(previous.get("period") or ""), str(previous.get("periodName") or ""))

    latest_num = _as_float(latest_value)
    previous_num = _as_float(previous_value)
    change = None
    if latest_num is not None and previous_num is not None:
        change = latest_num - previous_num

    unit = info.get("unit") or "value"
    frequency = info.get("frequency") or "unknown"
    title = info.get("title") or series_id
    category = info.get("category") or "macro_data"
    source_url = f"https://data.bls.gov/timeseries/{series_id}"

    if latest_value in (None, ""):
        summary = (
            f"BLS structured fetch attempted for {series_id}, but no readable observations were returned. "
            "Treat this as blank or incomplete evidence."
        )
        kind = "bls-data-warning"
        confidence = "low"
        evidence_status = "blank or incomplete BLS row"
    else:
        summary = (
            f"Latest BLS value for {series_id}: {_format_number(latest_value)} on {latest_date or 'n/a'} "
            f"({unit}, {frequency}). Prior value: {_format_number(previous_value)} on {previous_date or 'n/a'}; "
            f"change vs prior: {_format_change(change)}."
        )
        kind = "bls-data"
        confidence = "high"
        evidence_status = "readable BLS data row"

    metadata = {
        "series_id": series_id,
        "title": title,
        "latest_value": latest_value,
        "latest_date": latest_date,
        "previous_value": previous_value,
        "previous_date": previous_date,
        "change": change,
        "unit": unit,
        "units": unit,
        "frequency": frequency,
        "category": category,
        "source_url": source_url,
        "evidence_status": evidence_status,
        "topic": topic,
    }

    return {
        "id": f"bls-data-{index}-{series_id.lower()}",
        "brief_selection_id": f"bls-data-{index}-{series_id.lower()}",
        "brief_dedupe_key": f"bls:{series_id}:{latest_date}",
        "title": f"{series_id}: {title}",
        "summary": summary,
        "url": source_url,
        "source": "BLS",
        "kind": kind,
        "confidence": confidence,
        "source_type": "macro_data",
        "selectable": True,
        "needs_manual_search": False,
        "evidence_status": evidence_status,
        "metadata": metadata,
        **metadata,
    }


def build_bls_newsroom_items(topic: str, sources: Optional[Iterable[str]] = None, limit: int = 10) -> list[dict[str, Any]]:
    if not (_source_selected(sources, "bls") or _topic_mentions_bls(topic)):
        return []

    series_ids = _series_for_topic(topic)
    if not series_ids:
        return []

    data = _fetch_bls_series(series_ids)
    status = str(data.get("status") or "")
    if status and status.upper() != "REQUEST_SUCCEEDED":
        message = "; ".join(str(x) for x in data.get("message") or []) or status
        raise RuntimeError(f"BLS API request failed: {message}")

    series_rows = (data.get("Results") or {}).get("series") or []
    if not isinstance(series_rows, list):
        series_rows = []

    items = [_series_item(row, topic=topic, index=i) for i, row in enumerate(series_rows, start=1) if isinstance(row, dict)]
    return items[:limit]


def extend_results_with_bls(topic: str, sources: Optional[Iterable[str]], results: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    base = list(results or [])
    if not (_source_selected(sources, "bls") or _topic_mentions_bls(topic)):
        return base

    try:
        bls_items = build_bls_newsroom_items(topic, sources=sources)
    except Exception as exc:
        error_id = "bls-data-error"
        return [
            {
                "id": error_id,
                "brief_selection_id": error_id,
                "title": "BLS structured data unavailable",
                "summary": f"BLS UI integration could not build structured cards: {exc}",
                "url": "https://www.bls.gov/developers/",
                "source": "BLS",
                "kind": "bls-data-warning",
                "confidence": "low",
                "source_type": "macro_data",
                "selectable": True,
                "needs_manual_search": False,
                "evidence_status": "blank or incomplete BLS row",
                "metadata": {"connector": "bls", "error": str(exc)},
            },
            *base,
        ]

    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for item in [*bls_items, *base]:
        key = str(item.get("brief_dedupe_key") or item.get("id") or item.get("url") or item.get("title") or "")
        if key and key in seen:
            continue
        output.append(item)
        if key:
            seen.add(key)
    return output
