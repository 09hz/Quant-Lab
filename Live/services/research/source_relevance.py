from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Iterable

@dataclass(frozen=True)
class SourceRoute:
    source_id: str
    source_name: str
    relevance: str
    reason: str
    include: bool = True
    topics: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_relevant(self) -> bool:
        return self.include and self.relevance not in {"skip", "not-relevant"}

@dataclass(frozen=True)
class QueryProfile:
    original: str
    normalized: str
    topics: tuple[str, ...]
    tickers: tuple[str, ...]
    expanded_terms: tuple[str, ...]

SOURCE_NAMES = {
    "fred": "FRED", "bls": "BLS", "bea": "BEA", "fed": "Federal Reserve",
    "sec": "SEC EDGAR", "treasury": "Treasury Fiscal Data",
    "imf": "IMF", "worldbank": "World Bank", "wef": "World Economic Forum",
    "news": "General Economic News",
}

_STOP_TICKERS = {"CPI", "PCE", "GDP", "FOMC", "FED", "BLS", "BEA", "API", "USA", "USD", "SEC", "IMF", "WEF", "NEWS", "RATE", "RATES", "DEBT", "TIPS"}

def normalize_source_id(source: str) -> str:
    source = str(source or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "federalreserve": "fed", "frb": "fed", "federal_reserve": "fed",
        "edgar": "sec", "sec_edgar": "sec",
        "google": "news", "google_news": "news", "general_news": "news",
        "world_bank": "worldbank",
        "treasury_fiscal_data": "treasury", "fiscal_data": "treasury", "fiscaldata": "treasury",
    }
    return aliases.get(source, source)

def normalize_query(query: str) -> str:
    return " ".join(str(query or "").strip().split())

def extract_tickers(query: str) -> tuple[str, ...]:
    words = re.findall(r"\$?[A-Za-z]{1,8}", str(query or ""))
    tickers: list[str] = []
    for word in words:
        raw = word.strip("$")
        clean = raw.upper()
        if 1 <= len(clean) <= 5 and clean.isalpha() and raw == clean and clean not in _STOP_TICKERS:
            tickers.append(clean)
    return tuple(dict.fromkeys(tickers))

def classify_query(query: str) -> QueryProfile:
    normalized = normalize_query(query)
    lowered = normalized.lower()
    topics: set[str] = set()
    expanded: list[str] = [normalized] if normalized else []

    def has(*words: str) -> bool:
        return any(word in lowered for word in words)

    if has("inflation", "cpi", "pce", "consumer price", "core price", "deflator"):
        topics.update({"inflation", "macro"})
        expanded += ["inflation", "CPI", "Consumer Price Index", "core CPI", "PCE price index", "core PCE", "CPIAUCSL", "CPILFESL", "PCEPI"]

    if has("rate", "rates", "fed funds", "interest", "yield", "treasury yield", "fomc"):
        topics.update({"rates", "macro"})
        expanded += ["federal funds rate", "Fed funds", "Treasury yields", "FOMC", "FEDFUNDS"]

    if has("jobs", "employment", "unemployment", "payroll", "wages", "labor"):
        topics.update({"labor", "macro"})
        expanded += ["unemployment rate", "nonfarm payrolls", "wages", "labor market", "UNRATE", "PAYEMS"]

    if has("gdp", "growth", "recession", "nipa", "consumer spending", "income"):
        topics.update({"growth", "macro"})
        expanded += ["GDP", "real GDP", "NIPA", "personal income", "consumer spending"]

    if has("debt", "deficit", "outlays", "receipts", "spending", "treasury statement", "public debt", "fiscal", "interest expense"):
        topics.update({"fiscal", "treasury"})
        expanded += ["public debt", "federal deficit", "receipts", "outlays", "monthly treasury statement"]

    if has("filing", "10-k", "10q", "10-q", "8-k", "edgar", "sec filing", "earnings", "company facts"):
        topics.update({"filings", "company"})

    tickers = extract_tickers(normalized)
    if tickers:
        topics.add("company")

    if has("news", "article", "headline", "today", "latest"):
        topics.add("news")

    if not topics and normalized:
        topics.add("general")

    return QueryProfile(normalized, normalized, tuple(sorted(topics)), tickers, tuple(dict.fromkeys(t for t in expanded if str(t).strip())))

def route_source_for_query(source: str, query: str) -> SourceRoute:
    profile = classify_query(query)
    sid = normalize_source_id(source)
    topics = set(profile.topics)
    name = SOURCE_NAMES.get(sid, str(source or "Source"))

    def route(relevance: str, reason: str, include: bool = True) -> SourceRoute:
        return SourceRoute(sid, name, relevance, reason, include, profile.topics)

    if sid == "fred":
        if topics & {"inflation", "rates", "labor", "growth", "macro"}:
            return route("high", "FRED is relevant for economic time series such as CPI, PCE, rates, labor, GDP, and yields.")
        if topics & {"fiscal"}:
            return route("medium", "FRED may have related fiscal or debt series, but Treasury Fiscal Data is usually more direct.")
        return route("medium", "FRED can be useful for broad macro context.")
    if sid == "bls":
        if topics & {"inflation", "labor"}:
            return route("high", "BLS is relevant for CPI, employment, wages, unemployment, and labor statistics.")
        if topics & {"macro"}:
            return route("medium", "BLS may have related macro/labor series.")
        return route("skip", "BLS is usually not useful unless the query relates to CPI, jobs, wages, or labor.", False)
    if sid == "bea":
        if topics & {"inflation", "growth"}:
            return route("high", "BEA is relevant for PCE inflation, GDP, income, spending, and national accounts.")
        if topics & {"macro"}:
            return route("medium", "BEA may be useful for macro context, especially national accounts.")
        return route("skip", "BEA is usually not useful unless the query relates to GDP, PCE, income, or spending.", False)
    if sid == "fed":
        if topics & {"inflation", "rates", "macro"}:
            return route("high", "Federal Reserve materials are relevant for inflation, rates, FOMC, and monetary policy.")
        return route("medium", "Federal Reserve search may provide policy context if the query is economic.")
    if sid == "treasury":
        if topics & {"fiscal", "treasury"}:
            return route("high", "Fiscal Data is relevant for debt, deficit, receipts, outlays, Treasury statements, and federal fiscal datasets.")
        return route("skip", "Fiscal Data is not a general macro search engine; skip unless the query is about debt, deficits, spending, receipts, or Treasury fiscal datasets.", False)
    if sid == "sec":
        if topics & {"company", "filings"}:
            return route("high", "SEC EDGAR is relevant because the query appears to include a company, ticker, filing, or earnings context.")
        return route("skip", "SEC EDGAR is not usually relevant for macro-only topics unless a company/ticker/filing is included.", False)
    if sid == "news":
        return route("high", "General economic news can provide current articles; verify important facts with primary sources.")
    if sid in {"imf", "worldbank", "wef"}:
        if topics & {"macro", "growth", "inflation", "rates", "labor", "fiscal"}:
            return route("medium", f"{name} can provide broader economic context, but it may be less direct than primary U.S. data sources.")
        return route("low", f"{name} may be useful for broad context but is not a primary match for this query.")
    return route("low", "Unrecognized source; use as fallback only.")

def route_sources_for_query(query: str, source_ids: Iterable[str] | None = None, *, include_skipped: bool = True) -> list[SourceRoute]:
    requested = [normalize_source_id(s) for s in (source_ids or []) if str(s).strip()]
    if not requested:
        requested = ["fred", "bls", "bea", "fed", "treasury", "sec", "news", "imf", "worldbank", "wef"]
    routes = [route_source_for_query(source, query) for source in dict.fromkeys(requested)]
    return routes if include_skipped else [route for route in routes if route.is_relevant]
