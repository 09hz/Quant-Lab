"""Newsroom result hygiene helpers.

This module keeps the Newsroom light:
- keep structured/direct official results visible and selectable
- downgrade generic source-search pages to manual-search helpers
- hide known broken/page-not-found results by default
- avoid adding low-quality links to AI research briefs
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse


BROKEN_TEXT_MARKERS = (
    "404",
    "page not found",
    "not found",
    "does not exist",
    "cannot be found",
    "error 404",
    "invalid url",
    "broken link",
)

MANUAL_SEARCH_URL_MARKERS = (
    "/search",
    "search?",
    "searchresults",
    "query/results",
    "fedsearch.org",
    "news.google.com/search",
    "google.com/search",
    "site_search",
    "search_api_fulltext",
)

DIRECT_URL_MARKERS = (
    "fred.stlouisfed.org/series/",
    "data.bls.gov/timeseries/",
    "sec.gov/Archives/",
    "sec.gov/ixviewer/",
    "bea.gov/data/",
    "bea.gov/news/",
    "fiscaldata.treasury.gov/datasets/",
    "federalreserve.gov/newsevents/",
    "federalreserve.gov/monetarypolicy/",
)


@dataclass(frozen=True)
class HygieneCounts:
    visible: int = 0
    selectable: int = 0
    hidden: int = 0
    manual_search: int = 0
    structured: int = 0
    direct: int = 0


def _text_blob(item: dict[str, Any]) -> str:
    parts = [
        item.get("source"),
        item.get("title"),
        item.get("summary"),
        item.get("url"),
        item.get("status"),
        item.get("confidence"),
        item.get("result_quality"),
        item.get("hygiene_status"),
    ]
    return " ".join(str(x or "") for x in parts).lower()


def _url(item: dict[str, Any]) -> str:
    return str(item.get("url") or item.get("href") or "").strip()


def _hostname(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def is_broken_result(item: dict[str, Any]) -> bool:
    """Return True when a result is likely broken enough to hide by default."""
    blob = _text_blob(item)
    status = str(item.get("status") or item.get("validation_status") or "").lower()
    http_status = str(item.get("http_status") or item.get("status_code") or "")

    if status in {"failed", "broken", "invalid", "not_found", "page_not_found"}:
        return True
    if http_status.startswith("4") or http_status.startswith("5"):
        return True
    return any(marker in blob for marker in BROKEN_TEXT_MARKERS)


def is_manual_search_result(item: dict[str, Any]) -> bool:
    """Return True for generic source-search pages that need human follow-up."""
    url = _url(item).lower()
    title = str(item.get("title") or "").lower()
    source = str(item.get("source") or "").lower()
    result_type = str(item.get("type") or item.get("result_type") or "").lower()
    confidence = str(item.get("confidence") or "").lower()

    if result_type in {"manual_search", "search", "source_search"}:
        return True
    if confidence in {"manual_search", "low"}:
        return True
    if "manual search" in title:
        return True

    if any(marker in url for marker in MANUAL_SEARCH_URL_MARKERS):
        # Google News is intentionally article discovery, but the search page itself
        # should not be selectable as a research fact for the AI brief.
        return True

    # SEC/FiscalData generic pages are often useful entry points but weak evidence.
    if source in {"sec", "sec edgar", "fiscaldata", "fiscal data"} and (
        not any(marker in url for marker in DIRECT_URL_MARKERS)
    ):
        return True

    return False


def is_structured_result(item: dict[str, Any]) -> bool:
    """Return True for result cards backed by fetched structured data."""
    source = str(item.get("source") or "").lower()
    result_type = str(item.get("type") or item.get("result_type") or "").lower()
    blob = _text_blob(item)

    if result_type in {"structured", "fred_observation", "fred_series", "data"}:
        return True
    if item.get("structured") is True or item.get("observations"):
        return True
    if source == "fred" and any(key in blob for key in ("latest value", "prior value", "series:", "frequency")):
        return True
    return False


def is_direct_official_result(item: dict[str, Any]) -> bool:
    """Return True for direct official pages/data pages, not generic searches."""
    url = _url(item).lower()
    return any(marker in url for marker in DIRECT_URL_MARKERS)


def _append_note(summary: str, note: str) -> str:
    summary = str(summary or "").strip()
    if note.lower() in summary.lower():
        return summary
    if not summary:
        return note
    return f"{summary} {note}"


def apply_result_hygiene(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize a single Newsroom result card for display/selection."""
    clean = deepcopy(item)
    clean.setdefault("visible", True)
    clean.setdefault("selectable", bool(clean.get("selectable", True)))

    if is_broken_result(clean):
        clean["visible"] = False
        clean["selectable"] = False
        clean["result_quality"] = "hidden_broken"
        clean["hygiene_status"] = "hidden"
        clean["hygiene_reason"] = "Page-not-found or invalid result hidden by Newsroom hygiene."
        clean["summary"] = _append_note(
            clean.get("summary", ""),
            "Hidden: page-not-found or invalid result.",
        )
        return clean

    if is_structured_result(clean):
        clean["visible"] = True
        clean["selectable"] = True
        clean["result_quality"] = clean.get("result_quality") or "structured_data"
        clean["hygiene_status"] = "structured"
        clean["hygiene_reason"] = "Structured official data result."
        return clean

    if is_direct_official_result(clean):
        clean["visible"] = True
        clean["selectable"] = bool(clean.get("selectable", True))
        clean["result_quality"] = clean.get("result_quality") or "direct_official"
        clean["hygiene_status"] = "direct"
        clean["hygiene_reason"] = "Direct official source page."
        return clean

    if is_manual_search_result(clean):
        clean["visible"] = True
        clean["selectable"] = False
        clean["result_quality"] = "manual_search"
        clean["hygiene_status"] = "manual_search"
        clean["hygiene_reason"] = "Generic source-search page; use manually, but do not add to AI brief."
        title = str(clean.get("title") or "").strip()
        if title and "manual search" not in title.lower():
            clean["title"] = f"{title} · Manual search needed"
        clean["summary"] = _append_note(
            clean.get("summary", ""),
            "Manual search needed: this is a source search page, not a direct research result. It is not added to the AI brief by default.",
        )
        return clean

    # Default: visible but not automatically trusted if existing logic marked it low.
    confidence = str(clean.get("confidence") or "").lower()
    if confidence in {"low", "manual_search", "failed"}:
        clean["selectable"] = False
        clean["result_quality"] = clean.get("result_quality") or "low_confidence"
        clean["hygiene_status"] = "low_confidence"
        clean["hygiene_reason"] = "Low-confidence result kept visible but not selectable."
        clean["summary"] = _append_note(
            clean.get("summary", ""),
            "Low-confidence result: verify manually before using.",
        )
    else:
        clean["hygiene_status"] = clean.get("hygiene_status") or "ok"
        clean["result_quality"] = clean.get("result_quality") or "general"

    return clean


def _sort_key(item: dict[str, Any]) -> tuple[int, str, str]:
    status = str(item.get("hygiene_status") or "").lower()
    quality = str(item.get("result_quality") or "").lower()
    source = str(item.get("source") or "").lower()
    title = str(item.get("title") or "").lower()

    if status == "structured" or quality == "structured_data":
        rank = 0
    elif status == "direct" or quality == "direct_official":
        rank = 1
    elif status == "ok":
        rank = 2
    elif status == "manual_search":
        rank = 8
    elif status == "hidden":
        rank = 9
    else:
        rank = 5
    return (rank, source, title)


def clean_newsroom_results(results: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Apply hygiene rules and sort best evidence above weak/manual results."""
    cleaned = [apply_result_hygiene(item) for item in (results or []) if isinstance(item, dict)]
    return sorted(cleaned, key=_sort_key)


def hygiene_counts(results: list[dict[str, Any]] | None) -> HygieneCounts:
    items = results or []
    visible = sum(1 for item in items if item.get("visible", True))
    selectable = sum(1 for item in items if item.get("visible", True) and item.get("selectable"))
    hidden = sum(1 for item in items if not item.get("visible", True))
    manual = sum(1 for item in items if item.get("hygiene_status") == "manual_search")
    structured = sum(1 for item in items if item.get("hygiene_status") == "structured")
    direct = sum(1 for item in items if item.get("hygiene_status") == "direct")
    return HygieneCounts(
        visible=visible,
        selectable=selectable,
        hidden=hidden,
        manual_search=manual,
        structured=structured,
        direct=direct,
    )


def summarize_hygiene(results: list[dict[str, Any]] | None) -> str:
    counts = hygiene_counts(results)
    parts: list[str] = []
    if counts.structured:
        parts.append(f"{counts.structured} structured")
    if counts.direct:
        parts.append(f"{counts.direct} direct official")
    if counts.manual_search:
        parts.append(f"{counts.manual_search} manual-search")
    if counts.hidden:
        parts.append(f"{counts.hidden} hidden broken")
    return ", ".join(parts)
