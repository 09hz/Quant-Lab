"""
FRED research connector for Newsroom.

This connector is intentionally app-owned. The AI advisor should receive only
curated summaries produced by this module, not direct arbitrary API access.

Environment:
    FRED_API_KEY=your_key
    RESEARCH_FRED_TIMEOUT_SECONDS=8
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen


FRED_API_BASE_URL = "https://api.stlouisfed.org/fred"
FRED_SERIES_PAGE_BASE_URL = "https://fred.stlouisfed.org/series"


@dataclass(frozen=True)
class FredSeriesCandidate:
    """A curated FRED series candidate for a research query."""

    series_id: str
    title: str
    topic: str
    relevance: str
    source_url: str
    reason: str = ""


@dataclass(frozen=True)
class FredObservationSummary:
    """Compact AI-safe summary of the latest FRED observations."""

    series_id: str
    title: str
    units: str
    frequency: str
    latest_date: Optional[str]
    latest_value: Optional[float]
    previous_date: Optional[str]
    previous_value: Optional[float]
    change: Optional[float]
    observation_count: int
    source_url: str
    fetched_at: str
    error: Optional[str] = None


_CURATED_SERIES: Dict[str, List[Dict[str, str]]] = {
    "inflation": [
        {
            "series_id": "CPIAUCSL",
            "title": "Consumer Price Index for All Urban Consumers: All Items",
            "reason": "headline CPI inflation context",
        },
        {
            "series_id": "CPILFESL",
            "title": "Consumer Price Index for All Urban Consumers: All Items Less Food and Energy",
            "reason": "core CPI inflation context",
        },
        {
            "series_id": "PCEPI",
            "title": "Personal Consumption Expenditures: Chain-type Price Index",
            "reason": "PCE inflation context",
        },
        {
            "series_id": "PCEPILFE",
            "title": "Personal Consumption Expenditures Excluding Food and Energy",
            "reason": "core PCE inflation context",
        },
        {
            "series_id": "T10YIE",
            "title": "10-Year Breakeven Inflation Rate",
            "reason": "market-implied inflation expectations",
        },
        {
            "series_id": "FEDFUNDS",
            "title": "Effective Federal Funds Rate",
            "reason": "policy-rate backdrop for inflation",
        },
    ],
    "rates": [
        {
            "series_id": "FEDFUNDS",
            "title": "Effective Federal Funds Rate",
            "reason": "short-rate policy context",
        },
        {
            "series_id": "DGS2",
            "title": "Market Yield on U.S. Treasury Securities at 2-Year Constant Maturity",
            "reason": "front-end Treasury yield context",
        },
        {
            "series_id": "DGS10",
            "title": "Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity",
            "reason": "long-rate Treasury yield context",
        },
        {
            "series_id": "T10Y2Y",
            "title": "10-Year Treasury Constant Maturity Minus 2-Year Treasury Constant Maturity",
            "reason": "yield curve slope context",
        },
        {
            "series_id": "SOFR",
            "title": "Secured Overnight Financing Rate",
            "reason": "overnight funding-rate context",
        },
    ],
    "labor": [
        {
            "series_id": "UNRATE",
            "title": "Unemployment Rate",
            "reason": "headline labor-market slack",
        },
        {
            "series_id": "PAYEMS",
            "title": "All Employees, Total Nonfarm",
            "reason": "nonfarm payroll employment",
        },
        {
            "series_id": "CIVPART",
            "title": "Labor Force Participation Rate",
            "reason": "labor-force participation context",
        },
        {
            "series_id": "ICSA",
            "title": "Initial Claims",
            "reason": "weekly jobless claims context",
        },
    ],
    "growth": [
        {
            "series_id": "GDP",
            "title": "Gross Domestic Product",
            "reason": "nominal economic growth",
        },
        {
            "series_id": "GDPC1",
            "title": "Real Gross Domestic Product",
            "reason": "real economic growth",
        },
        {
            "series_id": "A191RL1Q225SBEA",
            "title": "Real Gross Domestic Product Percent Change",
            "reason": "real GDP growth rate",
        },
        {
            "series_id": "INDPRO",
            "title": "Industrial Production: Total Index",
            "reason": "industrial activity context",
        },
    ],
    "housing": [
        {
            "series_id": "HOUST",
            "title": "Housing Starts: Total New Privately Owned Housing Units Started",
            "reason": "housing construction activity",
        },
        {
            "series_id": "MSPUS",
            "title": "Median Sales Price of Houses Sold for the United States",
            "reason": "home-price context",
        },
        {
            "series_id": "MORTGAGE30US",
            "title": "30-Year Fixed Rate Mortgage Average in the United States",
            "reason": "mortgage rate context",
        },
    ],
    "consumer": [
        {
            "series_id": "RSAFS",
            "title": "Advance Retail Sales: Retail Trade",
            "reason": "retail-sales demand context",
        },
        {
            "series_id": "UMCSENT",
            "title": "University of Michigan: Consumer Sentiment",
            "reason": "consumer sentiment context",
        },
        {
            "series_id": "PCE",
            "title": "Personal Consumption Expenditures",
            "reason": "consumer spending context",
        },
    ],
    "liquidity": [
        {
            "series_id": "WALCL",
            "title": "Assets: Total Assets: Total Assets (Less Eliminations from Consolidation)",
            "reason": "Federal Reserve balance-sheet liquidity context",
        },
        {
            "series_id": "M2SL",
            "title": "M2",
            "reason": "money-supply context",
        },
        {
            "series_id": "RRPONTSYD",
            "title": "Overnight Reverse Repurchase Agreements: Treasury Securities Sold by the Federal Reserve",
            "reason": "reverse-repo liquidity context",
        },
    ],
}


_TOPIC_KEYWORDS: Dict[str, Iterable[str]] = {
    "inflation": (
        "inflation",
        "cpi",
        "consumer price",
        "pce",
        "core pce",
        "core cpi",
        "prices",
        "deflator",
        "breakeven",
    ),
    "rates": (
        "rate",
        "rates",
        "yield",
        "yields",
        "fed funds",
        "fomc",
        "treasury",
        "curve",
        "sofr",
        "interest",
    ),
    "labor": (
        "unemployment",
        "jobs",
        "payroll",
        "payrolls",
        "labor",
        "claims",
        "employment",
        "wages",
        "participation",
    ),
    "growth": (
        "gdp",
        "growth",
        "recession",
        "industrial production",
        "output",
        "economy",
    ),
    "housing": (
        "housing",
        "home",
        "homes",
        "mortgage",
        "starts",
        "building permits",
        "real estate",
    ),
    "consumer": (
        "retail",
        "consumer",
        "sentiment",
        "spending",
        "consumption",
        "sales",
    ),
    "liquidity": (
        "liquidity",
        "balance sheet",
        "money supply",
        "m2",
        "reverse repo",
        "fed balance",
    ),
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get_fred_api_key(env_var: str = "FRED_API_KEY") -> str:
    """Return the FRED API key from environment, or an empty string."""

    return str(os.environ.get(env_var, "") or "").strip()


def fred_series_url(series_id: str) -> str:
    """Return the human-readable FRED series page URL."""

    series_id = str(series_id or "").upper().strip()
    return f"{FRED_SERIES_PAGE_BASE_URL}/{series_id}"


def detect_fred_topics(query: str) -> List[str]:
    """Detect broad macro topics for a user query."""

    text = f" {str(query or '').lower()} "
    topics: List[str] = []

    for topic, keywords in _TOPIC_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            topics.append(topic)

    if not topics:
        # FRED is broadly macro-oriented. Keep a small default set instead of
        # pretending every topic is high-confidence.
        topics = ["inflation", "rates", "growth"]

    return topics


def curated_fred_candidates(query: str, limit: int = 8) -> List[FredSeriesCandidate]:
    """Return curated FRED series candidates for a query."""

    seen = set()
    candidates: List[FredSeriesCandidate] = []

    for topic in detect_fred_topics(query):
        for item in _CURATED_SERIES.get(topic, []):
            series_id = item["series_id"].upper()
            if series_id in seen:
                continue
            seen.add(series_id)
            candidates.append(
                FredSeriesCandidate(
                    series_id=series_id,
                    title=item["title"],
                    topic=topic,
                    relevance="high" if topic != "growth" else "medium",
                    source_url=fred_series_url(series_id),
                    reason=item.get("reason", ""),
                )
            )
            if len(candidates) >= limit:
                return candidates

    return candidates


def _api_get_json(
    endpoint: str,
    params: Dict[str, Any],
    *,
    timeout_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    """Call a FRED API endpoint and return parsed JSON."""

    timeout = float(timeout_seconds or os.environ.get("RESEARCH_FRED_TIMEOUT_SECONDS", 8) or 8)
    url = f"{FRED_API_BASE_URL}/{endpoint.lstrip('/')}"
    query = dict(params or {})
    query["file_type"] = "json"

    request_url = f"{url}?{urlencode(query)}"
    request = Request(
        request_url,
        headers={
            "User-Agent": "AlgoTrader-Newsroom/1.0 (+local research tool)",
            "Accept": "application/json",
        },
    )

    with urlopen(request, timeout=timeout) as response:
        payload = response.read().decode("utf-8", errors="replace")

    data = json.loads(payload)
    if isinstance(data, dict) and data.get("error_code"):
        raise RuntimeError(f"FRED API error {data.get('error_code')}: {data.get('error_message')}")
    return data


def search_fred_series(
    query: str,
    *,
    api_key: Optional[str] = None,
    limit: int = 10,
    timeout_seconds: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Search FRED series metadata using the official series/search endpoint."""

    key = api_key or get_fred_api_key()
    if not key:
        raise RuntimeError("FRED_API_KEY is not configured.")

    data = _api_get_json(
        "series/search",
        {
            "api_key": key,
            "search_text": str(query or "").strip(),
            "limit": max(1, int(limit or 10)),
            "order_by": "popularity",
            "sort_order": "desc",
        },
        timeout_seconds=timeout_seconds,
    )

    return list(data.get("seriess", []) or [])


def fetch_series_metadata(
    series_id: str,
    *,
    api_key: Optional[str] = None,
    timeout_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    """Fetch metadata for one FRED series."""

    key = api_key or get_fred_api_key()
    if not key:
        raise RuntimeError("FRED_API_KEY is not configured.")

    series_id = str(series_id or "").upper().strip()
    data = _api_get_json(
        "series",
        {"api_key": key, "series_id": series_id},
        timeout_seconds=timeout_seconds,
    )
    series_list = list(data.get("seriess", []) or [])
    if not series_list:
        raise RuntimeError(f"No FRED metadata returned for {series_id}.")
    return dict(series_list[0])


def fetch_series_observations(
    series_id: str,
    *,
    api_key: Optional[str] = None,
    limit: int = 12,
    observation_start: Optional[str] = None,
    timeout_seconds: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Fetch recent observations for one FRED series."""

    key = api_key or get_fred_api_key()
    if not key:
        raise RuntimeError("FRED_API_KEY is not configured.")

    params: Dict[str, Any] = {
        "api_key": key,
        "series_id": str(series_id or "").upper().strip(),
        "limit": max(1, int(limit or 12)),
        "sort_order": "desc",
    }
    if observation_start:
        params["observation_start"] = observation_start

    data = _api_get_json("series/observations", params, timeout_seconds=timeout_seconds)
    return list(data.get("observations", []) or [])


def _float_or_none(value: Any) -> Optional[float]:
    text = str(value or "").strip()
    if not text or text == ".":
        return None
    try:
        return float(text)
    except Exception:
        return None


def summarize_fred_series(
    series_id: str,
    *,
    title: Optional[str] = None,
    api_key: Optional[str] = None,
    observation_limit: int = 24,
    timeout_seconds: Optional[float] = None,
) -> FredObservationSummary:
    """Fetch metadata and observations and return an AI-safe summary."""

    series_id = str(series_id or "").upper().strip()
    fetched_at = _utc_now_iso()

    try:
        metadata = fetch_series_metadata(series_id, api_key=api_key, timeout_seconds=timeout_seconds)
        observations = fetch_series_observations(
            series_id,
            api_key=api_key,
            limit=observation_limit,
            timeout_seconds=timeout_seconds,
        )

        parsed: List[Dict[str, Any]] = []
        for observation in observations:
            numeric_value = _float_or_none(observation.get("value"))
            if numeric_value is None:
                continue
            parsed.append(
                {
                    "date": observation.get("date"),
                    "value": numeric_value,
                }
            )

        latest = parsed[0] if parsed else {}
        previous = parsed[1] if len(parsed) > 1 else {}
        latest_value = latest.get("value")
        previous_value = previous.get("value")
        change = (
            float(latest_value) - float(previous_value)
            if latest_value is not None and previous_value is not None
            else None
        )

        return FredObservationSummary(
            series_id=series_id,
            title=str(metadata.get("title") or title or series_id),
            units=str(metadata.get("units") or ""),
            frequency=str(metadata.get("frequency") or ""),
            latest_date=latest.get("date"),
            latest_value=latest_value,
            previous_date=previous.get("date"),
            previous_value=previous_value,
            change=change,
            observation_count=len(parsed),
            source_url=fred_series_url(series_id),
            fetched_at=fetched_at,
            error=None,
        )

    except Exception as exc:
        return FredObservationSummary(
            series_id=series_id,
            title=str(title or series_id),
            units="",
            frequency="",
            latest_date=None,
            latest_value=None,
            previous_date=None,
            previous_value=None,
            change=None,
            observation_count=0,
            source_url=fred_series_url(series_id),
            fetched_at=fetched_at,
            error=str(exc),
        )


def build_fred_research_brief(
    query: str,
    *,
    api_key: Optional[str] = None,
    max_series: int = 4,
    observation_limit: int = 24,
    timeout_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    """Build a compact structured FRED research brief for Newsroom/AI."""

    key = api_key or get_fred_api_key()
    candidates = curated_fred_candidates(query, limit=max_series)

    brief: Dict[str, Any] = {
        "source": "FRED",
        "query": str(query or "").strip(),
        "api_configured": bool(key),
        "generated_at": _utc_now_iso(),
        "candidates": [asdict(candidate) for candidate in candidates],
        "series_summaries": [],
        "warnings": [],
    }

    if not key:
        brief["warnings"].append(
            "FRED_API_KEY is not configured. Showing curated official FRED series links only."
        )
        return brief

    for candidate in candidates:
        summary = summarize_fred_series(
            candidate.series_id,
            title=candidate.title,
            api_key=key,
            observation_limit=observation_limit,
            timeout_seconds=timeout_seconds,
        )
        brief["series_summaries"].append(asdict(summary))

    return brief


def format_fred_brief_markdown(brief: Dict[str, Any]) -> str:
    """Format a FRED brief as human-readable Markdown."""

    lines: List[str] = []
    query = brief.get("query") or ""
    lines.append(f"# FRED Research Brief: {query}".strip())
    lines.append("")
    lines.append(f"Generated: {brief.get('generated_at', '')}")
    lines.append(f"API configured: {bool(brief.get('api_configured'))}")
    lines.append("")

    warnings = list(brief.get("warnings") or [])
    if warnings:
        lines.append("## Warnings")
        for warning in warnings:
            lines.append(f"- {warning}")
        lines.append("")

    summaries = list(brief.get("series_summaries") or [])
    if summaries:
        lines.append("## Series summaries")
        for summary in summaries:
            change = summary.get("change")
            change_text = "n/a" if change is None else f"{change:.4g}"
            latest_value = summary.get("latest_value")
            latest_text = "n/a" if latest_value is None else f"{latest_value:.6g}"
            lines.append(
                f"- **{summary.get('series_id')}** — {summary.get('title')}: "
                f"{latest_text} on {summary.get('latest_date') or 'n/a'} "
                f"({summary.get('units') or 'units n/a'}, change vs prior: {change_text}). "
                f"{summary.get('source_url')}"
            )
        lines.append("")

    candidates = list(brief.get("candidates") or [])
    if candidates:
        lines.append("## Candidate source links")
        for candidate in candidates:
            lines.append(
                f"- **{candidate.get('series_id')}** — {candidate.get('title')} "
                f"({candidate.get('reason') or 'curated series'}): {candidate.get('source_url')}"
            )
        lines.append("")

    return "\n".join(lines).strip() + "\n"
