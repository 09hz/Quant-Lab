from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable


@dataclass(frozen=True)
class ResearchSource:
    """Trusted research/news/data source registry entry."""

    key: str
    name: str
    category: str
    url: str
    description: str
    ai_use: str
    requires_key: bool = False
    enabled_by_default: bool = True
    priority: int = 50

    def to_dict(self) -> dict:
        return asdict(self)


class TrustedSourceRegistry:
    def __init__(self, sources: Iterable[ResearchSource] | None = None) -> None:
        self._sources: dict[str, ResearchSource] = {}
        for source in sources or []:
            self.add(source)

    def add(self, source: ResearchSource) -> None:
        self._sources[source.key] = source

    def __iter__(self):
        """Iterate over all sources for UI compatibility."""
        return iter(self.all(enabled_only=False))

    def __len__(self) -> int:
        return len(self._sources)

    def get(self, key: str) -> ResearchSource | None:
        return self._sources.get(key)

    def all(self, enabled_only: bool = False) -> list[ResearchSource]:
        values = list(self._sources.values())
        if enabled_only:
            values = [source for source in values if source.enabled_by_default]
        return sorted(values, key=lambda src: (src.priority, src.category, src.name))

    def to_manifest(self, enabled_only: bool = True) -> list[dict]:
        return [source.to_dict() for source in self.all(enabled_only=enabled_only)]

    def to_markdown(self, enabled_only: bool = True) -> str:
        lines = ["# Trusted Research Sources", ""]
        for source in self.all(enabled_only=enabled_only):
            locked = "requires key" if source.requires_key else "public/website"
            lines.append(f"## {source.name}")
            lines.append(f"- Key: `{source.key}`")
            lines.append(f"- Category: {source.category}")
            lines.append(f"- Access: {locked}")
            lines.append(f"- URL: {source.url}")
            lines.append(f"- Why AI may use it: {source.ai_use}")
            lines.append("")
        return "\n".join(lines).strip() + "\n"


def build_default_source_registry() -> TrustedSourceRegistry:
    return TrustedSourceRegistry(
        [
            ResearchSource(
                key="fred",
                name="FRED / Federal Reserve Bank of St. Louis",
                category="macro_data",
                url="https://fred.stlouisfed.org/",
                description="Economic time series, rates, inflation, labor, credit and macro indicators.",
                ai_use="Use for macro backdrop, trend context, rate/inflation/labor series references.",
                requires_key=True,
                priority=10,
            ),
            ResearchSource(
                key="bea",
                name="U.S. Bureau of Economic Analysis",
                category="macro_data",
                url="https://www.bea.gov/",
                description="GDP, income, spending, corporate profits and national accounts.",
                ai_use="Use for GDP/growth/income/spending context and longer-term economic framing.",
                requires_key=True,
                priority=15,
            ),
            ResearchSource(
                key="bls",
                name="U.S. Bureau of Labor Statistics",
                category="macro_data",
                url="https://www.bls.gov/",
                description="CPI, PPI, employment, unemployment, wages and labor statistics.",
                ai_use="Use for labor/inflation context and event risk around major releases.",
                requires_key=False,
                priority=20,
            ),
            ResearchSource(
                key="federal_reserve",
                name="Federal Reserve",
                category="central_bank",
                url="https://www.federalreserve.gov/",
                description="FOMC, monetary policy releases, speeches, reports and data.",
                ai_use="Use for policy-rate backdrop, central-bank communications and risk framing.",
                requires_key=False,
                priority=25,
            ),
            ResearchSource(
                key="treasury",
                name="U.S. Treasury Fiscal Data",
                category="macro_data",
                url="https://fiscaldata.treasury.gov/",
                description="Treasury fiscal datasets and public debt data.",
                ai_use="Use for rates/fiscal/debt context when discussing macro conditions.",
                requires_key=False,
                priority=30,
            ),
            ResearchSource(
                key="sec_edgar",
                name="SEC EDGAR",
                category="company_filings",
                url="https://www.sec.gov/edgar",
                description="Company filings, disclosures, 10-K, 10-Q, 8-K and ownership reports.",
                ai_use="Use for company-specific disclosure context, but do not assume live price impact.",
                requires_key=False,
                priority=35,
            ),
            ResearchSource(
                key="imf",
                name="International Monetary Fund",
                category="global_macro",
                url="https://www.imf.org/",
                description="Global macro outlooks, financial stability, country data and reports.",
                ai_use="Use for global macro and cross-country economic context.",
                requires_key=False,
                priority=40,
            ),
            ResearchSource(
                key="world_bank",
                name="World Bank",
                category="global_macro",
                url="https://www.worldbank.org/",
                description="Global development, rates, country and economic datasets.",
                ai_use="Use for country/macro backdrop and long-term economic context.",
                requires_key=False,
                priority=45,
            ),
            ResearchSource(
                key="wef",
                name="World Economic Forum",
                category="global_macro",
                url="https://www.weforum.org/",
                description="Global economic, geopolitical, technology and policy themes.",
                ai_use="Use only as high-level thematic context, not as primary market data.",
                requires_key=False,
                priority=60,
            ),
        ]
    )
