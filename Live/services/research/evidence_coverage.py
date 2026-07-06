from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class EvidenceRecommendation:
    rec_id: str
    bucket: str
    title: str
    source: str
    kind: str
    confidence: str
    url: str
    summary: str
    query: str = ""
    source_type: str = "official"
    evidence_role: str = "recommended-missing-evidence"


BUCKETS: tuple[dict[str, Any], ...] = (
    {
        "key": "inflation",
        "label": "Inflation",
        "tokens": ("CPIAUCSL", "CPILFESL", "PCEPI", "PCEPILFE", "CPI", "core CPI", "PCE inflation", "core PCE"),
        "recommendations": (
            EvidenceRecommendation("rec-fred-cpiaucsl", "inflation", "FRED CPIAUCSL - Consumer Price Index", "FRED", "official-data-recommendation", "high", "https://fred.stlouisfed.org/series/CPIAUCSL", "Official FRED source candidate for headline CPI.", "CPIAUCSL headline CPI inflation"),
            EvidenceRecommendation("rec-fred-cpilfesl", "inflation", "FRED CPILFESL - Core CPI", "FRED", "official-data-recommendation", "high", "https://fred.stlouisfed.org/series/CPILFESL", "Official FRED source candidate for core CPI.", "CPILFESL core CPI inflation"),
            EvidenceRecommendation("rec-fred-pcepi", "inflation", "FRED PCEPI - PCE Price Index", "FRED", "official-data-recommendation", "high", "https://fred.stlouisfed.org/series/PCEPI", "Official FRED source candidate for PCE inflation.", "PCEPI PCE inflation"),
            EvidenceRecommendation("rec-fred-pcepilfe", "inflation", "FRED PCEPILFE - Core PCE", "FRED", "official-data-recommendation", "high", "https://fred.stlouisfed.org/series/PCEPILFE", "Official FRED source candidate for core PCE inflation.", "PCEPILFE core PCE inflation"),
        ),
    },
    {
        "key": "rates",
        "label": "Rates / Fed policy",
        "tokens": ("DGS2", "DGS10", "FEDFUNDS", "T10Y2Y", "2Y", "10Y", "yield curve", "Fed funds"),
        "recommendations": (
            EvidenceRecommendation("rec-fred-dgs2", "rates", "FRED DGS2 - 2-Year Treasury Yield", "FRED", "official-data-recommendation", "high", "https://fred.stlouisfed.org/series/DGS2", "Official FRED source candidate for 2Y Treasury rate pressure.", "DGS2 2 year treasury yield"),
            EvidenceRecommendation("rec-fred-dgs10", "rates", "FRED DGS10 - 10-Year Treasury Yield", "FRED", "official-data-recommendation", "high", "https://fred.stlouisfed.org/series/DGS10", "Official FRED source candidate for 10Y Treasury rate pressure.", "DGS10 10 year treasury yield"),
            EvidenceRecommendation("rec-fred-fedfunds", "rates", "FRED FEDFUNDS - Effective Federal Funds Rate", "FRED", "official-data-recommendation", "high", "https://fred.stlouisfed.org/series/FEDFUNDS", "Official FRED source candidate for Fed policy rate context.", "FEDFUNDS effective federal funds rate"),
            EvidenceRecommendation("rec-fred-t10y2y", "rates", "FRED T10Y2Y - 10Y minus 2Y Treasury Spread", "FRED", "official-data-recommendation", "high", "https://fred.stlouisfed.org/series/T10Y2Y", "Official FRED source candidate for yield curve pressure.", "T10Y2Y yield curve spread"),
        ),
    },
    {
        "key": "risk",
        "label": "Market risk / index confirmation",
        "tokens": ("VIXCLS", "VIX", "SP500", "NASDAQCOM", "NASDAQ", "S&P 500", "SPY", "QQQ"),
        "recommendations": (
            EvidenceRecommendation("rec-fred-vixcls", "risk", "FRED VIXCLS - CBOE Volatility Index", "FRED", "official-data-recommendation", "high", "https://fred.stlouisfed.org/series/VIXCLS", "Official FRED source candidate for market risk sentiment.", "VIXCLS volatility risk sentiment"),
            EvidenceRecommendation("rec-fred-sp500", "risk", "FRED SP500 - S&P 500 Index", "FRED", "official-data-recommendation", "high", "https://fred.stlouisfed.org/series/SP500", "Official FRED source candidate for broad equity confirmation.", "SP500 S&P 500 index confirmation"),
            EvidenceRecommendation("rec-fred-nasdaqcom", "risk", "FRED NASDAQCOM - NASDAQ Composite", "FRED", "official-data-recommendation", "high", "https://fred.stlouisfed.org/series/NASDAQCOM", "Official FRED source candidate for NASDAQ confirmation.", "NASDAQCOM Nasdaq composite confirmation"),
        ),
    },
    {
        "key": "labor_sentiment",
        "label": "Labor / sentiment",
        "tokens": ("PAYEMS", "UNRATE", "UMCSENT", "employment", "unemployment", "consumer sentiment"),
        "recommendations": (
            EvidenceRecommendation("rec-fred-payems", "labor_sentiment", "FRED PAYEMS - Nonfarm Payrolls", "FRED", "official-data-recommendation", "high", "https://fred.stlouisfed.org/series/PAYEMS", "Official FRED source candidate for labor breadth.", "PAYEMS nonfarm payroll labor breadth"),
            EvidenceRecommendation("rec-fred-unrate", "labor_sentiment", "FRED UNRATE - Unemployment Rate", "FRED", "official-data-recommendation", "high", "https://fred.stlouisfed.org/series/UNRATE", "Official FRED source candidate for labor slack.", "UNRATE unemployment labor slack"),
            EvidenceRecommendation("rec-fred-umcsent", "labor_sentiment", "FRED UMCSENT - Consumer Sentiment", "FRED", "official-data-recommendation", "high", "https://fred.stlouisfed.org/series/UMCSENT", "Official FRED source candidate for consumer sentiment.", "UMCSENT consumer sentiment"),
        ),
    },
    {
        "key": "manufacturing",
        "label": "Manufacturing / industrial cycle",
        "tokens": ("IPMAN", "INDPRO", "DGORDER", "AMTMNO", "MANEMP", "industrial production", "durable goods", "new orders", "manufacturing"),
        "recommendations": (
            EvidenceRecommendation("rec-fred-ipman", "manufacturing", "FRED IPMAN - Manufacturing Industrial Production", "FRED", "official-data-recommendation", "high", "https://fred.stlouisfed.org/series/IPMAN", "Official FRED source candidate for manufacturing production.", "IPMAN manufacturing industrial production"),
            EvidenceRecommendation("rec-fred-indpro", "manufacturing", "FRED INDPRO - Industrial Production", "FRED", "official-data-recommendation", "high", "https://fred.stlouisfed.org/series/INDPRO", "Official FRED source candidate for broad industrial production.", "INDPRO industrial production"),
            EvidenceRecommendation("rec-fred-dgorder", "manufacturing", "FRED DGORDER - Durable Goods Orders", "FRED", "official-data-recommendation", "high", "https://fred.stlouisfed.org/series/DGORDER", "Official FRED source candidate for durable goods orders.", "DGORDER durable goods orders"),
            EvidenceRecommendation("rec-fred-amtmno", "manufacturing", "FRED AMTMNO - Manufacturers New Orders", "FRED", "official-data-recommendation", "high", "https://fred.stlouisfed.org/series/AMTMNO", "Official FRED source candidate for manufacturing new orders.", "AMTMNO manufacturers new orders"),
        ),
    },
    {
        "key": "energy_geo",
        "label": "Energy / geopolitical risk",
        "tokens": ("DCOILWTICO", "oil", "crude", "XLE", "geopolitical", "shipping", "sanctions", "energy risk"),
        "recommendations": (
            EvidenceRecommendation("rec-fred-dcoilwtico", "energy_geo", "FRED DCOILWTICO - WTI Crude Oil Price", "FRED", "official-data-recommendation", "high", "https://fred.stlouisfed.org/series/DCOILWTICO", "Official FRED source candidate for oil risk-premium proxy.", "DCOILWTICO WTI crude oil price"),
            EvidenceRecommendation("rec-news-oil-geo", "energy_geo", "News search - oil geopolitical shipping sanctions risk", "News", "news-search-recommendation", "medium", "https://news.google.com/search?q=oil%20geopolitical%20shipping%20sanctions%20risk%20markets", "Review current news candidates for geopolitical/oil risk. Approve only sources that contain useful confirmed facts.", "oil geopolitical shipping sanctions market risk current quarter", "news"),
        ),
    },
    {
        "key": "sector_guidance",
        "label": "Sector / current-quarter guidance",
        "tokens": ("NVDA", "AMD", "MSFT", "guidance", "earnings", "current quarter", "SMH", "XLI"),
        "recommendations": (
            EvidenceRecommendation("rec-sec-nvda-guidance", "sector_guidance", "SEC / filings search - NVDA current-quarter guidance", "SEC EDGAR", "filing-search-recommendation", "medium", "https://www.sec.gov/edgar/search/#/q=NVDA%2520guidance", "Review filings/source candidates for NVDA current-quarter guidance.", "NVDA current quarter earnings guidance SEC filing", "filing"),
            EvidenceRecommendation("rec-sec-amd-guidance", "sector_guidance", "SEC / filings search - AMD current-quarter guidance", "SEC EDGAR", "filing-search-recommendation", "medium", "https://www.sec.gov/edgar/search/#/q=AMD%2520guidance", "Review filings/source candidates for AMD current-quarter guidance.", "AMD current quarter earnings guidance SEC filing", "filing"),
            EvidenceRecommendation("rec-sec-msft-guidance", "sector_guidance", "SEC / filings search - MSFT current-quarter guidance", "SEC EDGAR", "filing-search-recommendation", "medium", "https://www.sec.gov/edgar/search/#/q=MSFT%2520guidance", "Review filings/source candidates for MSFT current-quarter guidance.", "MSFT current quarter earnings guidance SEC filing", "filing"),
            EvidenceRecommendation("rec-news-semiconductor-guidance", "sector_guidance", "News search - semiconductors AI demand current-quarter guidance", "News", "news-search-recommendation", "medium", "https://news.google.com/search?q=semiconductors%20AI%20demand%20current-quarter%20guidance%20NVDA%20AMD%20MSFT", "Review current news candidates for semiconductor/AI current-quarter guidance.", "semiconductors AI demand current quarter guidance NVDA AMD MSFT", "news"),
        ),
    },
)


AI_OR_GAP_KINDS = (
    "quant-research-playbook",
    "research-analyst",
    "ai-answer",
    "ai-summary",
    "missing-evidence",
    "evidence-coverage",
)

AI_OR_GAP_SOURCES = (
    "research analyst",
    "ai research analyst",
    "strategy ai",
    "openai",
)

GAP_TEXT_MARKERS = (
    "missing evidence",
    "remaining gaps",
    "still need",
    "not present",
    "insufficient evidence",
    "must be researched",
    "need confirmed",
    "needed to determine",
    "does not include",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _item_text(item: dict[str, Any]) -> str:
    parts = [
        item.get("id"),
        item.get("title"),
        item.get("source"),
        item.get("kind"),
        item.get("url"),
        item.get("summary"),
        item.get("topic"),
        item.get("validity"),
        item.get("source_role"),
        item.get("evidence_role"),
    ]
    return " ".join(_clean(part) for part in parts if _clean(part))


def _is_approved_recommendation(item: dict[str, Any]) -> bool:
    if not isinstance(item, dict):
        return False
    return bool(item.get("approved_recommendation") or item.get("recommendation_approved_at"))


def _is_source_like(item: dict[str, Any]) -> bool:
    if not isinstance(item, dict):
        return False

    if _is_approved_recommendation(item):
        return True

    source = _clean(item.get("source")).lower()
    kind = _clean(item.get("kind")).lower()
    role = _clean(item.get("evidence_role") or item.get("source_role")).lower()
    title = _clean(item.get("title")).lower()
    summary = _clean(item.get("summary")).lower()

    if any(marker in kind for marker in AI_OR_GAP_KINDS):
        return False
    if source in AI_OR_GAP_SOURCES:
        return False
    if "recommended-missing-evidence" in role and not _is_approved_recommendation(item):
        return False

    combined_gap_text = " ".join([title, summary])
    if any(marker in combined_gap_text for marker in GAP_TEXT_MARKERS):
        if source in AI_OR_GAP_SOURCES or "playbook" in kind or "analyst" in kind:
            return False

    if source in {"fred", "bls", "bea", "federal reserve", "sec edgar", "treasury", "news", "google news"}:
        return True

    url = _clean(item.get("url")).lower()
    if "fred.stlouisfed.org/series/" in url:
        return True
    if "sec.gov" in url:
        return True
    if url and source and source not in AI_OR_GAP_SOURCES:
        return True

    return False


def _bucket_present(items: list[dict[str, Any]], bucket: dict[str, Any]) -> bool:
    tokens = tuple(str(token).lower() for token in bucket.get("tokens", ()))
    for item in items:
        if not _is_source_like(item):
            continue
        text = _item_text(item).lower()
        if any(token and token in text for token in tokens):
            return True
    return False


def analyze_evidence_coverage(items: list[dict[str, Any]] | None) -> dict[str, Any]:
    clean_items = [item for item in (items or []) if isinstance(item, dict)]
    present = []
    missing = []

    for bucket in BUCKETS:
        row = {
            "key": bucket["key"],
            "label": bucket["label"],
        }
        if _bucket_present(clean_items, bucket):
            present.append(row)
        else:
            missing.append(row)

    return {
        "generated_at": _now_iso(),
        "present": present,
        "missing": missing,
        "present_keys": [item["key"] for item in present],
        "missing_keys": [item["key"] for item in missing],
        "source_like_item_count": sum(1 for item in clean_items if _is_source_like(item)),
        "input_item_count": len(clean_items),
    }


def build_recommended_evidence_sources(items: list[dict[str, Any]] | None, *, max_per_bucket: int = 8) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    coverage = analyze_evidence_coverage(items or [])
    missing_keys = set(coverage.get("missing_keys", []))
    recommendations: list[dict[str, Any]] = []

    for bucket in BUCKETS:
        if bucket["key"] not in missing_keys:
            continue
        for rec in tuple(bucket.get("recommendations", ()))[:max_per_bucket]:
            row = asdict(rec)
            row.update(
                {
                    "id": rec.rec_id,
                    "visible": True,
                    "selectable": True,
                    "user_addable": True,
                    "approved_recommendation": False,
                    "recommendation_generated_at": coverage["generated_at"],
                }
            )
            recommendations.append(row)

    return coverage, recommendations


def recommendations_to_options(recommendations: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    options = []
    for rec in recommendations or []:
        if not isinstance(rec, dict):
            continue
        rec_id = _clean(rec.get("id") or rec.get("rec_id"))
        if not rec_id:
            continue
        label = f"{_clean(rec.get('bucket'))}: {_clean(rec.get('source'))} - {_clean(rec.get('title'))}"
        options.append({"label": label, "value": rec_id})
    return options


def coverage_to_markdown(coverage: dict[str, Any], recommendations: list[dict[str, Any]] | None = None) -> str:
    lines = ["## Evidence Coverage", ""]
    for item in coverage.get("present", []):
        lines.append(f"- {item.get('label')}: present")
    for item in coverage.get("missing", []):
        lines.append(f"- {item.get('label')}: missing")

    lines.extend(["", "## Pending Recommendations", ""])
    recs = list(recommendations or [])
    if not recs:
        lines.append("_No missing-evidence recommendations are pending._")
    else:
        for rec in recs:
            lines.append(f"- [{rec.get('bucket')}] {rec.get('source')} - {rec.get('title')}")
    return "\n".join(lines)
