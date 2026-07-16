from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote_plus

from services.research.query_planner import PlannedQuery, plan_query
from services.research.source_relevance import classify_query, route_source_for_query, normalize_source_id, route_sources_for_query

@dataclass(frozen=True)
class ResearchLink:
    title: str
    source: str
    url: str
    result_type: str = "search"
    summary: str = ""
    confidence: str = "manual-search"
    needs_manual_search: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

def _q(text: str) -> str:
    return quote_plus(str(text or "").strip())

def _first_ticker(planned: PlannedQuery) -> str | None:
    return planned.tickers[0] if planned.tickers else None

def build_source_search_links(query: str, source_ids: list[str] | tuple[str, ...] | None = None, *, include_skipped: bool = True) -> list[ResearchLink]:
    planned = plan_query(query, selected_sources=source_ids)
    profile = classify_query(query)
    sources = [normalize_source_id(s) for s in (source_ids or []) if str(s).strip()]
    if not sources:
        sources = [route.source_id for route in route_sources_for_query(query, include_skipped=False)]

    links: list[ResearchLink] = []
    for source in dict.fromkeys(sources):
        route = route_source_for_query(source, query)
        if not route.is_relevant:
            if include_skipped:
                links.append(ResearchLink(
                    title=f"Skipped {route.source_name}: not relevant for '{profile.normalized or 'this query'}'",
                    source=route.source_name,
                    url="",
                    result_type="skipped",
                    summary=route.reason,
                    confidence="not-relevant",
                    metadata={"source_id": route.source_id, "relevance": route.relevance, "selectable": False},
                ))
            continue
        links.extend(_links_for_source(planned, source, route.relevance, route.reason))
    return links

def _series_link(series_id: str, label: str, summary: str, *, confidence: str = "high") -> ResearchLink:
    return ResearchLink(
        title=f"FRED series: {label} ({series_id})",
        source="FRED",
        url=f"https://fred.stlouisfed.org/series/{series_id}",
        result_type="official-series",
        summary=summary,
        confidence=confidence,
        metadata={"series_id": series_id, "selectable": True},
    )

def _links_for_source(planned: PlannedQuery, source: str, relevance: str, reason: str) -> list[ResearchLink]:
    profile = classify_query(planned.normalized)
    topics = set(profile.topics)
    text = planned.as_search_text() or planned.normalized
    query = _q(text)
    short_query = _q(planned.normalized)
    ticker = _first_ticker(planned)
    source = normalize_source_id(source)

    if source == "fred":
        links: list[ResearchLink] = []
        if topics & {"inflation"}:
            links += [
                _series_link("CPIAUCSL", "Consumer Price Index", "CPI is a common inflation reference."),
                _series_link("CPILFESL", "Core CPI", "Core CPI excludes food and energy and is often used for trend inflation."),
                _series_link("PCEPI", "PCE Price Index", "PCE is a major inflation measure watched by policymakers."),
            ]
        if topics & {"rates"}:
            links.append(_series_link("FEDFUNDS", "Effective Federal Funds Rate", "Policy-rate context for rate-sensitive strategies."))
        if topics & {"labor"}:
            links += [
                _series_link("UNRATE", "Unemployment Rate", "Labor-market context."),
                _series_link("PAYEMS", "Nonfarm Payrolls", "Employment trend context."),
            ]
        if topics & {"growth"}:
            links.append(_series_link("GDPC1", "Real Gross Domestic Product", "Growth/recession context."))
        links.append(ResearchLink(
            f"FRED series search: {planned.normalized}",
            "FRED",
            f"https://fred.stlouisfed.org/searchresults/?search_type=series&search={query}",
            "official-search",
            "FRED topic-specific series search. Prefer the direct series cards above when available.",
            "medium",
            metadata={"relevance": relevance, "reason": reason, "selectable": True},
        ))
        return links

    if source == "bls":
        if topics & {"inflation"}:
            return [
                ResearchLink("BLS CPI topic page", "BLS", "https://www.bls.gov/cpi/", "official-topic-page", "Official BLS CPI page. Use for inflation/CPI context.", "high", metadata={"selectable": True}),
                ResearchLink(f"BLS CPI/search: {planned.normalized}", "BLS", f"https://www.bls.gov/search/query/results?cx=013738036195919377644%3A6ih0hfrgl50&q={query}", "official-search", "BLS search for CPI/inflation materials.", "medium", True, {"selectable": True}),
            ]
        if topics & {"labor"}:
            return [
                ResearchLink("BLS unemployment topic page", "BLS", "https://www.bls.gov/cps/", "official-topic-page", "BLS labor force and unemployment data.", "high", metadata={"selectable": True}),
                ResearchLink(f"BLS labor search: {planned.normalized}", "BLS", f"https://www.bls.gov/search/query/results?cx=013738036195919377644%3A6ih0hfrgl50&q={query}", "official-search", "BLS search for labor/employment materials.", "medium", True, {"selectable": True}),
            ]
        return [ResearchLink(f"BLS search: {planned.normalized}", "BLS", f"https://www.bls.gov/search/query/results?cx=013738036195919377644%3A6ih0hfrgl50&q={query}", "official-search", reason, "manual-search", True, {"selectable": True})]

    if source == "bea":
        links = [ResearchLink(f"BEA site search: {planned.normalized}", "BEA", f"https://www.bea.gov/search?search_api_fulltext={short_query}", "official-search", "BEA site search. BEA results often require choosing a dataset/table.", "manual-search", True, {"selectable": True})]
        if topics & {"growth"}:
            links.insert(0, ResearchLink("BEA GDP data page", "BEA", "https://www.bea.gov/data/gdp/gross-domestic-product", "official-topic-page", "Official BEA GDP page for growth context.", "high", metadata={"selectable": True}))
        if topics & {"inflation"}:
            links.insert(0, ResearchLink("BEA PCE price index data page", "BEA", "https://www.bea.gov/data/personal-consumption-expenditures-price-index", "official-topic-page", "Official BEA PCE price index page for inflation context.", "medium", metadata={"selectable": True}))
        return links

    if source == "fed":
        return [ResearchLink(f"Federal Reserve search: {planned.normalized}", "Federal Reserve", f"https://www.fedsearch.org/board_public/search?text={short_query}", "official-search", "Federal Reserve Board search result. Good for FOMC, speeches, policy, rates, and inflation materials.", "medium", metadata={"selectable": True})]

    if source == "treasury":
        if topics & {"fiscal", "treasury"}:
            return [
                ResearchLink("Fiscal Data: Debt to the Penny", "Treasury Fiscal Data", "https://fiscaldata.treasury.gov/datasets/debt-to-the-penny/", "official-dataset", "Daily total public debt dataset.", "high", metadata={"selectable": True}),
                ResearchLink("Fiscal Data: Monthly Treasury Statement", "Treasury Fiscal Data", "https://fiscaldata.treasury.gov/datasets/monthly-treasury-statement/", "official-dataset", "Monthly receipts, outlays, deficit/surplus dataset.", "high", metadata={"selectable": True}),
            ]
        return []

    if source == "sec":
        if ticker:
            return [ResearchLink(f"SEC EDGAR company search: {ticker}", "SEC EDGAR", f"https://www.sec.gov/edgar/search/#/q={_q(ticker)}&category=custom&entityName={_q(ticker)}", "official-search", "SEC EDGAR company filing search.", "high", metadata={"ticker": ticker, "selectable": True})]
        return [ResearchLink(f"SEC EDGAR search: {planned.normalized}", "SEC EDGAR", f"https://www.sec.gov/edgar/search/#/q={short_query}", "official-search", "SEC EDGAR filing search. Best when the query includes a company/ticker/filing topic.", "manual-search", True, {"selectable": True})]

    if source == "news":
        return [ResearchLink(f"Google News search: {planned.normalized}", "Google News", f"https://news.google.com/search?q={short_query}&hl=en-US&gl=US&ceid=US:en", "news-search", "General news discovery. Verify important claims with primary/official sources.", "medium", metadata={"selectable": True})]

    if source == "imf":
        return [ResearchLink(f"IMF search: {planned.normalized}", "IMF", f"https://www.imf.org/en/Search#q={short_query}&sort=relevancy", "institution-search", "IMF search for global macro reports and financial stability context.", "manual-search", True, {"selectable": True})]
    if source == "worldbank":
        return [ResearchLink(f"World Bank search: {planned.normalized}", "World Bank", f"https://www.worldbank.org/en/search?q={short_query}", "institution-search", "World Bank search for indicators, country data, and macro context.", "manual-search", True, {"selectable": True})]
    if source == "wef":
        return [ResearchLink(f"World Economic Forum search: {planned.normalized}", "World Economic Forum", f"https://www.weforum.org/search/?query={short_query}", "institution-search", "WEF search for broad economic themes and reports. Treat as context, not primary data.", "manual-search", True, {"selectable": True})]
    return [ResearchLink(f"{source} fallback search: {planned.normalized}", source, f"https://www.google.com/search?q={_q(source + ' ' + planned.normalized)}", "fallback-search", "Fallback search for an unrecognized source.", "low", True, {"selectable": True})]
