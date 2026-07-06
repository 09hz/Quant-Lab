from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class ResearchScopeSeries:
    series_id: str
    label: str
    category: str
    evidence_role: str
    source: str = "FRED"
    url: str = ""


_BASE_SERIES: tuple[ResearchScopeSeries, ...] = (
    ResearchScopeSeries("CPIAUCSL", "Consumer Price Index: All Items", "inflation", "confirmed macro inflation proxy", url="https://fred.stlouisfed.org/series/CPIAUCSL"),
    ResearchScopeSeries("CPILFESL", "Consumer Price Index: All Items Less Food and Energy", "inflation", "confirmed core inflation proxy", url="https://fred.stlouisfed.org/series/CPILFESL"),
    ResearchScopeSeries("PCEPI", "Personal Consumption Expenditures Price Index", "inflation", "confirmed PCE inflation proxy", url="https://fred.stlouisfed.org/series/PCEPI"),
    ResearchScopeSeries("PCEPILFE", "Core PCE Price Index", "inflation", "confirmed core PCE inflation proxy", url="https://fred.stlouisfed.org/series/PCEPILFE"),
    ResearchScopeSeries("FEDFUNDS", "Effective Federal Funds Rate", "policy_rates", "confirmed policy-rate context", url="https://fred.stlouisfed.org/series/FEDFUNDS"),
    ResearchScopeSeries("DGS2", "2-Year Treasury Constant Maturity Rate", "rates", "confirmed short-rate/yield proxy", url="https://fred.stlouisfed.org/series/DGS2"),
    ResearchScopeSeries("DGS10", "10-Year Treasury Constant Maturity Rate", "rates", "confirmed long-rate/yield proxy", url="https://fred.stlouisfed.org/series/DGS10"),
)

_SCOPE_SERIES: dict[str, tuple[ResearchScopeSeries, ...]] = {
    "financial_conditions": (
        ResearchScopeSeries("SP500", "S&P 500 Index", "financial_conditions", "broad equity risk proxy", url="https://fred.stlouisfed.org/series/SP500"),
        ResearchScopeSeries("VIXCLS", "CBOE Volatility Index: VIX", "financial_conditions", "equity volatility/risk proxy", url="https://fred.stlouisfed.org/series/VIXCLS"),
        ResearchScopeSeries("NFCI", "Chicago Fed National Financial Conditions Index", "financial_conditions", "financial conditions proxy", url="https://fred.stlouisfed.org/series/NFCI"),
        ResearchScopeSeries("BAA10Y", "Moody's Baa Corporate Bond Yield Relative to 10-Year Treasury", "financial_conditions", "credit spread proxy", url="https://fred.stlouisfed.org/series/BAA10Y"),
        ResearchScopeSeries("T10Y2Y", "10-Year Treasury Minus 2-Year Treasury Spread", "financial_conditions", "yield-curve proxy", url="https://fred.stlouisfed.org/series/T10Y2Y"),
    ),
    "tech_growth_proxy": (
        ResearchScopeSeries("NASDAQCOM", "NASDAQ Composite Index", "tech_growth_proxy", "tech/growth equity proxy", url="https://fred.stlouisfed.org/series/NASDAQCOM"),
        ResearchScopeSeries("SP500", "S&P 500 Index", "tech_growth_proxy", "broad equity comparison proxy", url="https://fred.stlouisfed.org/series/SP500"),
        ResearchScopeSeries("DGS2", "2-Year Treasury Constant Maturity Rate", "tech_growth_proxy", "discount-rate proxy", url="https://fred.stlouisfed.org/series/DGS2"),
        ResearchScopeSeries("DGS10", "10-Year Treasury Constant Maturity Rate", "tech_growth_proxy", "long discount-rate proxy", url="https://fred.stlouisfed.org/series/DGS10"),
        ResearchScopeSeries("VIXCLS", "CBOE Volatility Index: VIX", "tech_growth_proxy", "risk appetite proxy", url="https://fred.stlouisfed.org/series/VIXCLS"),
    ),
    "manufacturing_cycle": (
        ResearchScopeSeries("IPMAN", "Industrial Production: Manufacturing", "manufacturing_cycle", "manufacturing output proxy", url="https://fred.stlouisfed.org/series/IPMAN"),
        ResearchScopeSeries("INDPRO", "Industrial Production: Total Index", "manufacturing_cycle", "industrial activity proxy", url="https://fred.stlouisfed.org/series/INDPRO"),
        ResearchScopeSeries("MANEMP", "All Employees, Manufacturing", "manufacturing_cycle", "manufacturing labor proxy", url="https://fred.stlouisfed.org/series/MANEMP"),
        ResearchScopeSeries("AMTMNO", "Manufacturers' New Orders: Total Manufacturing", "manufacturing_cycle", "manufacturing demand/order proxy", url="https://fred.stlouisfed.org/series/AMTMNO"),
        ResearchScopeSeries("DGORDER", "Manufacturers' New Orders: Durable Goods", "manufacturing_cycle", "durable-goods demand proxy", url="https://fred.stlouisfed.org/series/DGORDER"),
        ResearchScopeSeries("ICSA", "Initial Claims", "manufacturing_cycle", "labor-cycle risk proxy", url="https://fred.stlouisfed.org/series/ICSA"),
    ),
    "consumer_demand": (
        ResearchScopeSeries("RSAFS", "Advance Retail Sales: Retail and Food Services", "consumer_demand", "consumer spending proxy", url="https://fred.stlouisfed.org/series/RSAFS"),
        ResearchScopeSeries("PCE", "Personal Consumption Expenditures", "consumer_demand", "consumer demand proxy", url="https://fred.stlouisfed.org/series/PCE"),
        ResearchScopeSeries("UMCSENT", "University of Michigan Consumer Sentiment", "consumer_demand", "consumer sentiment proxy", url="https://fred.stlouisfed.org/series/UMCSENT"),
        ResearchScopeSeries("PAYEMS", "All Employees, Total Nonfarm", "consumer_demand", "labor market proxy", url="https://fred.stlouisfed.org/series/PAYEMS"),
        ResearchScopeSeries("UNRATE", "Unemployment Rate", "consumer_demand", "labor slack proxy", url="https://fred.stlouisfed.org/series/UNRATE"),
    ),
    "quarter_outlook": (
        ResearchScopeSeries("SP500", "S&P 500 Index", "quarter_outlook", "broad equity current-quarter proxy", url="https://fred.stlouisfed.org/series/SP500"),
        ResearchScopeSeries("NASDAQCOM", "NASDAQ Composite Index", "quarter_outlook", "tech/growth current-quarter proxy", url="https://fred.stlouisfed.org/series/NASDAQCOM"),
        ResearchScopeSeries("FEDFUNDS", "Effective Federal Funds Rate", "quarter_outlook", "policy-rate context", url="https://fred.stlouisfed.org/series/FEDFUNDS"),
        ResearchScopeSeries("DGS10", "10-Year Treasury Constant Maturity Rate", "quarter_outlook", "long-rate context", url="https://fred.stlouisfed.org/series/DGS10"),
        ResearchScopeSeries("VIXCLS", "CBOE Volatility Index: VIX", "quarter_outlook", "risk/volatility context", url="https://fred.stlouisfed.org/series/VIXCLS"),
        ResearchScopeSeries("INDPRO", "Industrial Production: Total Index", "quarter_outlook", "industrial cycle context", url="https://fred.stlouisfed.org/series/INDPRO"),
        ResearchScopeSeries("AMTMNO", "Manufacturers' New Orders: Total Manufacturing", "quarter_outlook", "manufacturing orders context", url="https://fred.stlouisfed.org/series/AMTMNO"),
        ResearchScopeSeries("PAYEMS", "All Employees, Total Nonfarm", "quarter_outlook", "labor market context", url="https://fred.stlouisfed.org/series/PAYEMS"),
    ),
}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").lower().split())


def infer_research_scopes(*, question: str = "", topic: str = "", symbol: str = "") -> list[str]:
    text = _clean(" ".join(part for part in (question, topic, symbol) if part))
    scopes: list[str] = ["base_macro"]

    if any(term in text for term in ("tech", "nasdaq", "growth", "semiconductor", "software", "ai", "nvda", "msft", "aapl", "amd")):
        scopes.append("tech_growth_proxy")
    if any(term in text for term in ("manufacturing", "factory", "industrial", "orders", "durable", "pmi", "production")):
        scopes.append("manufacturing_cycle")
    if any(term in text for term in ("quarter", "bullish", "bearish", "outlook", "current", "q1", "q2", "q3", "q4")):
        scopes.append("quarter_outlook")
    if any(term in text for term in ("market", "rates", "yield", "credit", "spread", "volatility", "financial conditions", "fed")):
        scopes.append("financial_conditions")
    if any(term in text for term in ("consumer", "demand", "retail", "spending", "jobs", "employment", "unemployment")):
        scopes.append("consumer_demand")

    if "market impact" in text and "financial_conditions" not in scopes:
        scopes.append("financial_conditions")

    return scopes


def plan_research_scope(*, question: str = "", topic: str = "", symbol: str = "", max_series: int = 24) -> dict[str, Any]:
    scopes = infer_research_scopes(question=question, topic=topic, symbol=symbol)
    series: list[ResearchScopeSeries] = []
    seen: set[str] = set()

    def add_many(items: tuple[ResearchScopeSeries, ...]) -> None:
        for item in items:
            if item.series_id in seen:
                continue
            seen.add(item.series_id)
            series.append(item)

    add_many(_BASE_SERIES)
    for scope in scopes:
        if scope == "base_macro":
            continue
        add_many(_SCOPE_SERIES.get(scope, ()))

    if max_series and len(series) > max_series:
        series = series[:max_series]

    return {
        "schema_version": "1.0",
        "scopes": scopes,
        "series": [asdict(item) for item in series],
        "evidence_labels": ["confirmed", "proxy-only", "missing"],
        "notes": [
            "FRED macro/market series can support current macro and proxy context.",
            "NASDAQ/SP500/VIX/rates are market proxies, not company-specific tech fundamentals.",
            "Manufacturing FRED series are cycle proxies, not individual company guidance.",
        ],
    }
