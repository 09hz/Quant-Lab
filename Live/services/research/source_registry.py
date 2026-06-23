from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class ResearchSource:
    id: str
    name: str
    category: str
    url: str
    description: str
    reliability: str = "official"
    api_url: str | None = None
    rss_url: str | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_default_source_registry() -> list[ResearchSource]:
    return [
        ResearchSource(
            id="fred",
            name="FRED",
            category="macro_data",
            url="https://fred.stlouisfed.org/",
            api_url="https://fred.stlouisfed.org/docs/api/fred/",
            rss_url="https://fred.stlouisfed.org/releases/feeds",
            description="Federal Reserve Bank of St. Louis economic time-series database.",
            reliability="official",
            notes="Useful for rates, inflation, labor, GDP, money supply, spreads, and macro context.",
        ),
        ResearchSource(
            id="federal_reserve",
            name="Federal Reserve",
            category="central_bank",
            url="https://www.federalreserve.gov/",
            rss_url="https://www.federalreserve.gov/feeds/press_all.xml",
            description="Federal Reserve policy, speeches, press releases, and monetary policy materials.",
            reliability="official",
        ),
        ResearchSource(
            id="bea",
            name="BEA",
            category="macro_data",
            url="https://www.bea.gov/",
            api_url="https://apps.bea.gov/api/signup/",
            rss_url="https://www.bea.gov/news/glance",
            description="Bureau of Economic Analysis data including GDP, income, trade, and industry data.",
            reliability="official",
        ),
        ResearchSource(
            id="bls",
            name="BLS",
            category="labor_inflation",
            url="https://www.bls.gov/",
            api_url="https://www.bls.gov/developers/",
            rss_url="https://www.bls.gov/feed/",
            description="Bureau of Labor Statistics data including CPI, PPI, jobs, wages, and productivity.",
            reliability="official",
        ),
        ResearchSource(
            id="sec_edgar",
            name="SEC EDGAR",
            category="company_filings",
            url="https://www.sec.gov/edgar",
            api_url="https://www.sec.gov/search-filings/edgar-application-programming-interfaces",
            description="Company filings, 10-K, 10-Q, 8-K, ownership and other disclosure data.",
            reliability="official",
            notes="Respect SEC fair-access policies and identify your app if using automated requests.",
        ),
        ResearchSource(
            id="treasury_fiscal_data",
            name="U.S. Treasury Fiscal Data",
            category="fiscal_rates",
            url="https://fiscaldata.treasury.gov/",
            api_url="https://fiscaldata.treasury.gov/api-documentation/",
            description="U.S. Treasury public datasets including debt, rates, receipts, and fiscal data.",
            reliability="official",
        ),
        ResearchSource(
            id="imf",
            name="IMF",
            category="global_macro",
            url="https://www.imf.org/",
            description="International Monetary Fund global macroeconomic reports, datasets, and analysis.",
            reliability="institutional",
        ),
        ResearchSource(
            id="world_bank",
            name="World Bank",
            category="global_macro",
            url="https://www.worldbank.org/",
            api_url="https://datahelpdesk.worldbank.org/knowledgebase/articles/889392",
            description="Global development and macro datasets.",
            reliability="institutional",
        ),
        ResearchSource(
            id="world_economic_forum",
            name="World Economic Forum",
            category="global_context",
            url="https://www.weforum.org/",
            rss_url="https://www.weforum.org/agenda/feed/",
            description="Global economic, technology, policy, risk, and business commentary.",
            reliability="institutional",
            notes="Use as context/commentary, not as a primary market-data source.",
        ),
        ResearchSource(
            id="cnbc_economy",
            name="CNBC Economy",
            category="general_news",
            url="https://www.cnbc.com/economy/",
            rss_url="https://www.cnbc.com/id/20910258/device/rss/rss.html",
            description="General market/economy news feed.",
            reliability="news",
        ),
        ResearchSource(
            id="marketwatch_topstories",
            name="MarketWatch Top Stories",
            category="general_news",
            url="https://www.marketwatch.com/",
            rss_url="https://feeds.content.dowjones.io/public/rss/mw_topstories",
            description="General market and economic news feed.",
            reliability="news",
        ),
    ]


def get_default_source_registry() -> dict[str, ResearchSource]:
    return {source.id: source for source in build_default_source_registry()}


def source_manifest_text() -> str:
    lines = ["# Trusted Research Source Registry", ""]
    for source in build_default_source_registry():
        lines.append(f"## {source.name}")
        lines.append(f"- id: {source.id}")
        lines.append(f"- category: {source.category}")
        lines.append(f"- reliability: {source.reliability}")
        lines.append(f"- url: {source.url}")
        if source.api_url:
            lines.append(f"- api: {source.api_url}")
        if source.rss_url:
            lines.append(f"- feed: {source.rss_url}")
        lines.append(f"- description: {source.description}")
        if source.notes:
            lines.append(f"- notes: {source.notes}")
        lines.append("")
    return "\n".join(lines)
