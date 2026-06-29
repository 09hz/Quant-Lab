from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen


FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"


@dataclass(frozen=True)
class MacroAnchorSeries:
    series_id: str
    title: str
    category: str
    role: str
    units_hint: str = ""


# Mandatory macro anchors for market-impact and current-quarter questions.
# These are deliberately broad because Research Analyst questions often span
# inflation, policy, risk appetite, tech/growth, manufacturing, and demand.
MACRO_ANCHOR_SERIES: tuple[MacroAnchorSeries, ...] = (
    # Inflation anchors
    MacroAnchorSeries("CPIAUCSL", "Consumer Price Index for All Urban Consumers: All Items", "inflation", "headline CPI", "index"),
    MacroAnchorSeries("CPILFESL", "Consumer Price Index for All Urban Consumers: All Items Less Food and Energy", "inflation", "core CPI", "index"),
    MacroAnchorSeries("PCEPI", "Personal Consumption Expenditures: Chain-type Price Index", "inflation", "headline PCE price index", "index"),
    MacroAnchorSeries("PCEPILFE", "Personal Consumption Expenditures Excluding Food and Energy (Chain-Type Price Index)", "inflation", "core PCE price index", "index"),

    # Policy and rates anchors
    MacroAnchorSeries("FEDFUNDS", "Effective Federal Funds Rate", "policy", "policy-rate anchor", "percent"),
    MacroAnchorSeries("DGS2", "Market Yield on U.S. Treasury Securities at 2-Year Constant Maturity", "rates", "front-end rate proxy", "percent"),
    MacroAnchorSeries("DGS10", "Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity", "rates", "long-rate proxy", "percent"),
    MacroAnchorSeries("T10Y2Y", "10-Year Treasury Constant Maturity Minus 2-Year Treasury Constant Maturity", "rates", "yield-curve proxy", "percentage points"),

    # Financial conditions and risk anchors
    MacroAnchorSeries("SP500", "S&P 500", "market_risk", "broad equity proxy", "index"),
    MacroAnchorSeries("NASDAQCOM", "NASDAQ Composite Index", "tech_proxy", "tech/growth proxy", "index"),
    MacroAnchorSeries("VIXCLS", "CBOE Volatility Index: VIX", "market_risk", "equity-volatility proxy", "index"),
    MacroAnchorSeries("NFCI", "Chicago Fed National Financial Conditions Index", "financial_conditions", "financial-conditions proxy", "index"),
    MacroAnchorSeries("BAA10Y", "Moody's Seasoned Baa Corporate Bond Yield Relative to Yield on 10-Year Treasury", "financial_conditions", "credit-spread proxy", "percentage points"),

    # Manufacturing and real-economy anchors
    MacroAnchorSeries("IPMAN", "Industrial Production: Manufacturing", "manufacturing", "manufacturing output proxy", "index"),
    MacroAnchorSeries("INDPRO", "Industrial Production: Total Index", "manufacturing", "total industrial-production proxy", "index"),
    MacroAnchorSeries("AMTMNO", "Manufacturers' New Orders: Total Manufacturing", "manufacturing", "manufacturing orders proxy", "millions of dollars"),
    MacroAnchorSeries("DGORDER", "Manufacturers' New Orders: Durable Goods", "manufacturing", "durable-goods orders proxy", "millions of dollars"),
    MacroAnchorSeries("MANEMP", "All Employees, Manufacturing", "manufacturing", "manufacturing labor proxy", "thousands"),
    MacroAnchorSeries("ICSA", "Initial Claims", "labor_demand", "labor-softness proxy", "number"),

    # Consumer and demand anchors
    MacroAnchorSeries("RSAFS", "Retail Sales: Retail Trade", "demand", "retail demand proxy", "millions of dollars"),
    MacroAnchorSeries("PCE", "Personal Consumption Expenditures", "demand", "consumer-spending proxy", "billions of dollars"),
    MacroAnchorSeries("PAYEMS", "All Employees, Total Nonfarm", "labor_demand", "labor-market breadth proxy", "thousands"),
    MacroAnchorSeries("UNRATE", "Unemployment Rate", "labor_demand", "labor-market slack proxy", "percent"),
    MacroAnchorSeries("UMCSENT", "University of Michigan: Consumer Sentiment", "demand", "consumer-sentiment proxy", "index"),
)


MANDATORY_CATEGORIES = (
    "inflation",
    "policy",
    "rates",
    "market_risk",
    "tech_proxy",
    "financial_conditions",
    "manufacturing",
    "demand",
    "labor_demand",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _clean_text(value: Any, *, max_len: int = 1200) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = " ".join(text.split())
    if len(text) > max_len:
        return text[: max_len - 1].rstrip() + "..."
    return text


def _load_env_if_available() -> None:
    try:
        from services.config.env_loader import load_env_file
    except Exception:
        return
    try:
        load_env_file(override=False)
    except TypeError:
        try:
            load_env_file()
        except Exception:
            pass
    except Exception:
        pass


def _fred_api_key() -> str:
    _load_env_if_available()
    return (
        os.getenv("FRED_API_KEY")
        or os.getenv("FRED_KEY")
        or os.getenv("FRED_APIKEY")
        or ""
    ).strip()


def _parse_float(value: Any) -> float | None:
    try:
        text = str(value).strip()
        if not text or text == ".":
            return None
        return float(text)
    except Exception:
        return None


def _round_value(value: float | None) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 6)
    except Exception:
        return None


def _fetch_fred_observations(series_id: str, *, api_key: str, limit: int = 16, timeout: float = 12.0) -> list[dict[str, Any]]:
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "sort_order": "desc",
        "limit": str(max(1, min(100, int(limit or 16)))),
    }
    url = FRED_OBSERVATIONS_URL + "?" + urlencode(params)
    with urlopen(url, timeout=timeout) as response:  # noqa: S310 - approved FRED endpoint only.
        payload = json.loads(response.read().decode("utf-8"))
    observations = payload.get("observations") or []
    if not isinstance(observations, list):
        return []
    parsed: list[dict[str, Any]] = []
    for obs in observations:
        if not isinstance(obs, dict):
            continue
        value = _parse_float(obs.get("value"))
        if value is None:
            continue
        parsed.append({"date": str(obs.get("date") or ""), "value": value})
    return parsed


def _trend_from_observations(observations_desc: list[dict[str, Any]]) -> dict[str, Any]:
    values = [obs for obs in observations_desc if _parse_float(obs.get("value")) is not None]
    if not values:
        return {
            "latest_date": "",
            "latest": None,
            "prior_date": "",
            "prior": None,
            "change_1": None,
            "change_3": None,
            "change_6": None,
            "observations_used": 0,
        }

    latest = values[0]
    latest_value = _parse_float(latest.get("value"))
    prior = values[1] if len(values) > 1 else {}
    prior_value = _parse_float(prior.get("value"))

    def delta(index: int) -> float | None:
        if latest_value is None or len(values) <= index:
            return None
        older = _parse_float(values[index].get("value"))
        if older is None:
            return None
        return latest_value - older

    return {
        "latest_date": str(latest.get("date") or ""),
        "latest": _round_value(latest_value),
        "prior_date": str(prior.get("date") or ""),
        "prior": _round_value(prior_value),
        "change_1": _round_value(delta(1)),
        "change_3": _round_value(delta(3)),
        "change_6": _round_value(delta(6)),
        "observations_used": len(values),
    }


def _trend_sentence(series: MacroAnchorSeries, trend: dict[str, Any]) -> str:
    latest = trend.get("latest")
    latest_date = trend.get("latest_date") or "unknown date"
    prior = trend.get("prior")
    prior_date = trend.get("prior_date") or "prior observation"
    change_1 = trend.get("change_1")
    change_3 = trend.get("change_3")
    change_6 = trend.get("change_6")

    parts = [f"{series.series_id} latest confirmed observation is {latest} on {latest_date}."]
    if prior is not None:
        parts.append(f"Prior observation was {prior} on {prior_date}; 1-period change is {change_1}.")
    if change_3 is not None:
        parts.append(f"3-period change is {change_3}.")
    if change_6 is not None:
        parts.append(f"6-period change is {change_6}.")
    parts.append(f"Use as {series.role}; units hint: {series.units_hint or 'see FRED series page'}.")
    return " ".join(parts)


def _item_from_series(series: MacroAnchorSeries, trend: dict[str, Any]) -> dict[str, Any]:
    summary = _trend_sentence(series, trend)
    url = f"https://fred.stlouisfed.org/series/{series.series_id}"
    return {
        "id": f"macro-anchor-{series.series_id}",
        "title": f"FRED structured macro anchor: {series.series_id} - {series.title}",
        "source": "FRED",
        "url": url,
        "summary": summary,
        "topic": "Research Analyst mandatory macro anchor",
        "kind": "fred-structured-macro-anchor",
        "confidence": "high",
        "validity": "high",
        "relevance": "high",
        "source_type": "official",
        "source_role": "mandatory-macro-anchor",
        "used_for_ai": True,
        "selectable": True,
        "published_at": trend.get("latest_date") or "",
        "metadata": {
            "connector": "fred",
            "series_id": series.series_id,
            "series_title": series.title,
            "anchor_category": series.category,
            "anchor_role": series.role,
            "units_hint": series.units_hint,
            "trend": trend,
            "confirmed_or_proxy": "confirmed" if series.category in {"inflation", "policy", "rates"} else "proxy-only",
        },
        "fetched_at": _now_iso(),
    }


def _coverage_summary_item(coverage: dict[str, Any], *, error: str | None = None) -> dict[str, Any]:
    complete = coverage.get("complete_categories") or []
    missing = coverage.get("missing_categories") or []
    summary_parts = [
        "Evidence coverage summary for Research Analyst macro anchors.",
        f"Complete categories: {', '.join(complete) if complete else 'none'}.",
        f"Missing categories: {', '.join(missing) if missing else 'none'}.",
    ]
    if error:
        summary_parts.append(f"Connector warning: {error}")
    return {
        "id": "macro-anchor-coverage-summary",
        "title": "Research Analyst evidence coverage summary",
        "source": "Research Analyst",
        "url": "",
        "summary": " ".join(summary_parts),
        "topic": "Evidence coverage",
        "kind": "macro-anchor-coverage-summary",
        "confidence": "medium",
        "validity": "medium",
        "relevance": "high",
        "source_type": "source",
        "source_role": "coverage-summary",
        "used_for_ai": True,
        "selectable": True,
        "metadata": {"coverage": coverage, "confirmed_or_proxy": "coverage-summary"},
        "fetched_at": _now_iso(),
    }


def _series_for_question(question: str, topic: str, symbol: str, *, max_items: int = 24) -> list[MacroAnchorSeries]:
    text = f"{question} {topic} {symbol}".lower()
    broad_keywords = (
        "market",
        "quarter",
        "bullish",
        "bearish",
        "mixed",
        "tech",
        "manufacturing",
        "sector",
        "inflation",
        "fed",
        "rates",
        "macro",
        "correlation",
        "impact",
    )
    wants_broad_scope = any(word in text for word in broad_keywords)

    if wants_broad_scope:
        planned = list(MACRO_ANCHOR_SERIES)
    else:
        planned = [
            series
            for series in MACRO_ANCHOR_SERIES
            if series.category in {"inflation", "policy", "rates", "market_risk"}
        ]

    max_items = max(4, min(32, int(max_items or 24)))
    return planned[:max_items]


def build_macro_anchor_evidence(
    *,
    question: str = "",
    topic: str = "",
    symbol: str = "",
    selected_sources: list[str] | tuple[str, ...] | None = None,
    max_items: int = 24,
) -> tuple[list[dict[str, Any]], dict[str, Any], str | None]:
    """
    Build structured macro anchor evidence for the Research Analyst.

    Returns:
        (items, coverage, error)
    """
    selected = {str(item).lower().strip() for item in (selected_sources or []) if str(item).strip()}
    fred_allowed = not selected or "fred" in selected
    series_plan = _series_for_question(question, topic, symbol, max_items=max_items)

    coverage: dict[str, Any] = {
        "schema_version": "1.0",
        "generated_at": _now_iso(),
        "required_categories": list(MANDATORY_CATEGORIES),
        "complete_categories": [],
        "missing_categories": list(MANDATORY_CATEGORIES),
        "series_requested": [series.series_id for series in series_plan],
        "series_loaded": [],
        "series_missing": [],
        "fred_allowed": fred_allowed,
    }

    if not fred_allowed:
        error = "FRED is not selected in the Newsroom source filter; mandatory macro anchors were skipped."
        return [_coverage_summary_item(coverage, error=error)], coverage, error

    api_key = _fred_api_key()
    if not api_key:
        error = "FRED_API_KEY is not configured; mandatory macro anchors could not load structured observations."
        return [_coverage_summary_item(coverage, error=error)], coverage, error

    items: list[dict[str, Any]] = []
    loaded_categories: set[str] = set()
    errors: list[str] = []

    for series in series_plan:
        try:
            observations = _fetch_fred_observations(series.series_id, api_key=api_key)
            trend = _trend_from_observations(observations)
            if trend.get("latest") is None:
                coverage["series_missing"].append(series.series_id)
                errors.append(f"{series.series_id}: no numeric observations returned")
                continue
            item = _item_from_series(series, trend)
            items.append(item)
            loaded_categories.add(series.category)
            coverage["series_loaded"].append(series.series_id)
        except Exception as exc:
            coverage["series_missing"].append(series.series_id)
            errors.append(f"{series.series_id}: {exc}")

    complete = [category for category in MANDATORY_CATEGORIES if category in loaded_categories]
    missing = [category for category in MANDATORY_CATEGORIES if category not in loaded_categories]
    coverage["complete_categories"] = complete
    coverage["missing_categories"] = missing

    error_text = "; ".join(errors[:8]) if errors else None
    return [_coverage_summary_item(coverage, error=error_text), *items], coverage, error_text


def summarize_macro_anchor_coverage(coverage: dict[str, Any]) -> str:
    if not isinstance(coverage, dict):
        return "Macro anchor coverage unavailable."

    complete = coverage.get("complete_categories") or []
    missing = coverage.get("missing_categories") or []
    loaded = coverage.get("series_loaded") or []
    missing_series = coverage.get("series_missing") or []

    return (
        f"Macro anchors loaded: {len(loaded)} series. "
        f"Complete categories: {', '.join(complete) if complete else 'none'}. "
        f"Missing categories: {', '.join(missing) if missing else 'none'}. "
        f"Missing series: {', '.join(missing_series[:10]) if missing_series else 'none'}."
    )
