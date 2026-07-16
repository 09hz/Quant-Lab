from __future__ import annotations
from dataclasses import dataclass, field
from typing import Iterable
import re

@dataclass(frozen=True)
class PlannedQuery:
    original: str
    normalized: str
    terms: tuple[str, ...] = field(default_factory=tuple)
    tickers: tuple[str, ...] = field(default_factory=tuple)
    source_hints: tuple[str, ...] = field(default_factory=tuple)

    def as_search_text(self) -> str:
        return " ".join(self.terms or (self.normalized,)).strip()

_MACRO_EXPANSIONS: dict[str, tuple[str, ...]] = {
    "inflation": ("inflation", "CPI", "Consumer Price Index", "core CPI", "PCE price index", "core PCE", "breakeven inflation"),
    "inflation rate": ("inflation rate", "CPI inflation", "Consumer Price Index", "PCE inflation", "core inflation", "Fed inflation target"),
    "rates": ("interest rates", "federal funds rate", "Treasury yield", "rate cuts", "rate hikes"),
    "fed": ("Federal Reserve", "FOMC", "monetary policy", "federal funds rate"),
    "jobs": ("employment", "unemployment rate", "nonfarm payrolls", "labor market", "wages"),
    "recession": ("recession risk", "yield curve", "GDP growth", "unemployment", "consumer sentiment"),
    "gdp": ("GDP", "real gross domestic product", "economic growth", "BEA GDP"),
}

def normalize_query(query: str) -> str:
    return " ".join(str(query or "").strip().split())

def re_split_words(text: str) -> list[str]:
    return re.findall(r"\$?[A-Za-z]{1,8}", str(text or ""))

def extract_tickers(query: str) -> tuple[str, ...]:
    words = re_split_words(query)
    tickers: list[str] = []
    stop = {"CPI", "PCE", "GDP", "FOMC", "FED", "SEC", "BLS", "BEA", "API", "USA", "US"}
    for word in words:
        raw = word.strip("$")
        clean = raw.upper()
        if 1 <= len(clean) <= 5 and clean.isalpha() and raw == clean and clean not in stop:
            tickers.append(clean)
    return tuple(dict.fromkeys(tickers))

def plan_query(query: str, *, selected_sources: Iterable[str] | None = None) -> PlannedQuery:
    normalized = normalize_query(query)
    lowered = normalized.lower()
    terms: list[str] = [normalized] if normalized else []
    for key, expansions in _MACRO_EXPANSIONS.items():
        if key in lowered:
            terms.extend(expansions)
    if lowered in {"inflation", "inflation rate"}:
        terms.extend(["CPIAUCSL", "CPILFESL", "PCEPI", "FEDFUNDS"])
    tickers = extract_tickers(normalized)
    source_hints: list[str] = []
    if any(word in lowered for word in ["inflation", "cpi", "pce", "rates", "fed"]):
        source_hints.extend(["fred", "bls", "bea", "federal_reserve"])
    if tickers or any(word in lowered for word in ["filing", "10-k", "10-q", "earnings", "sec"]):
        source_hints.extend(["sec_edgar"])
    if any(word in lowered for word in ["jobs", "unemployment", "wages", "payroll"]):
        source_hints.extend(["bls", "fred"])
    if any(word in lowered for word in ["gdp", "growth", "nipa"]):
        source_hints.extend(["bea", "fred"])
    if selected_sources:
        source_hints.extend(str(source).strip().lower() for source in selected_sources if str(source).strip())
    return PlannedQuery(
        original=str(query or ""),
        normalized=normalized,
        terms=tuple(dict.fromkeys(term for term in terms if term)),
        tickers=tickers,
        source_hints=tuple(dict.fromkeys(source_hints)),
    )
