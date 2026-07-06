from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse


LANDING_PATHS = {
    "",
    "/",
    "/home",
    "/index",
    "/index.html",
    "/search",
    "/search/",
    "/news",
    "/news/",
    "/data",
    "/data/",
    "/statistics",
    "/statistics/",
    "/economic-research",
    "/economic-research/",
}

SEARCH_HINTS = {
    "search",
    "query",
    "keyword",
    "keywords",
    "q",
    "s",
    "text",
    "term",
    "terms",
    "find",
    "results",
}

BAD_URL_SUBSTRINGS = {
    "google.com/search",
    "bing.com/search",
    "duckduckgo.com/",
    "/search?",
    "?search=",
    "?q=",
    "&q=",
    "site-search",
    "search-results",
}

PREFERRED_SOURCE_HINTS = {
    "SEC EDGAR": [
        "Prefer company filing pages, accession-number filing detail pages, or SEC companyfacts/submissions endpoints.",
        "Avoid generic sec.gov/search or sec.gov/edgar landing pages as evidence URLs.",
    ],
    "BLS": [
        "Prefer BLS series/data endpoint URLs, BLS API-backed series IDs, or specific release pages.",
        "Avoid generic bls.gov home/search pages.",
    ],
    "BEA": [
        "Prefer BEA API requests, dataset/table-specific pages, or release pages with table IDs.",
        "Avoid generic bea.gov data landing pages.",
    ],
    "Federal Reserve": [
        "Prefer FRED series pages, FRED graph CSV URLs, FOMC statement pages, or H.15/H.4.1 specific releases.",
        "Avoid generic federalreserve.gov search pages.",
    ],
    "Treasury": [
        "Prefer Treasury FiscalData API endpoints, auction pages, or yield curve data endpoints.",
        "Avoid generic treasury.gov landing/search pages.",
    ],
    "IMF": [
        "Prefer specific IMF data portal datasets, WEO table links, or article/report pages.",
        "Avoid generic IMF search pages.",
    ],
    "World Bank": [
        "Prefer World Bank indicator, country, or API URLs with indicator IDs.",
        "Avoid generic worldbank.org search results.",
    ],
    "WEF": [
        "Prefer specific WEF report/article pages with dates and titles.",
        "Avoid generic topic landing pages.",
    ],
    "General Economic News": [
        "Prefer specific article URLs with publisher/date/title.",
        "Avoid news homepages, tag pages, and search result pages.",
    ],
}


@dataclass(frozen=True)
class SourceQualityResult:
    url: str
    score: int
    grade: str
    flags: list[str]
    recommendation: str

    def as_dict(self) -> dict[str, object]:
        return {
            "url": self.url,
            "score": self.score,
            "grade": self.grade,
            "flags": " | ".join(self.flags),
            "recommendation": self.recommendation,
        }


def _is_likely_landing(parsed) -> bool:
    path = (parsed.path or "/").rstrip("/").lower()
    if path in LANDING_PATHS:
        return True
    short_parts = [p for p in path.split("/") if p]
    return len(short_parts) <= 1 and not parsed.query


def _has_search_query(parsed) -> bool:
    query = parse_qs(parsed.query or "")
    keys = {k.lower() for k in query}
    if keys & SEARCH_HINTS:
        return True
    haystack = f"{parsed.netloc}{parsed.path}?{parsed.query}".lower()
    return any(fragment in haystack for fragment in BAD_URL_SUBSTRINGS)


def grade_url(url: str) -> SourceQualityResult:
    raw = str(url or "").strip()
    flags: list[str] = []
    score = 100

    if not raw:
        return SourceQualityResult(raw, 0, "missing", ["empty_url"], "Replace with a specific source URL.")

    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        score -= 40
        flags.append("not_http_url")

    if parsed.scheme == "http":
        score -= 15
        flags.append("http_not_https")

    if _has_search_query(parsed):
        score -= 45
        flags.append("search_result_or_query_url")

    if _is_likely_landing(parsed):
        score -= 35
        flags.append("landing_or_home_page")

    path = (parsed.path or "").lower()
    if any(x in path for x in [".pdf", ".csv", ".json", ".xml"]):
        score += 10
        flags.append("specific_file_or_data_resource")

    if len([p for p in path.split("/") if p]) >= 3:
        score += 8
        flags.append("deep_link")

    if any(x in raw.lower() for x in ["series_id=", "/series/", "accession", "cik=", "indicator/", "dataset", "api"]):
        score += 10
        flags.append("structured_data_or_identifier")

    score = max(0, min(100, score))

    if score >= 85:
        grade = "excellent"
        recommendation = "Keep. This looks like a specific evidence URL."
    elif score >= 70:
        grade = "good"
        recommendation = "Usable. Prefer a deeper source URL if available."
    elif score >= 50:
        grade = "weak"
        recommendation = "Replace with a specific article, release, filing, table, series, CSV, API, or PDF URL."
    else:
        grade = "bad"
        recommendation = "Do not use as AI evidence. Replace this landing/search URL before sending to the analyst."

    return SourceQualityResult(raw, score, grade, flags, recommendation)


def should_send_to_ai_evidence(url: str, *, min_score: int = 70) -> bool:
    return grade_url(url).score >= min_score


def source_guidance(source_name: str) -> list[str]:
    return PREFERRED_SOURCE_HINTS.get(source_name, ["Prefer specific evidence URLs over landing or search pages."])
