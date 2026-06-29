# Research Analyst scope expansion hotfix 36h2

This hotfix replaces the failed 36h apply path when `Live/services/research/research_analyst_gap_fill.py` was missing.

## Adds

- `Live/services/research/research_analyst_scope.py`
- `Live/services/research/research_analyst_gap_fill.py`
- `Live/scripts/check_research_analyst_scope_expansion.py`

## Behavior

The Research Analyst supplemental source path now places structured official FRED data before generic search/discovery links.

Structured scope includes:

- inflation/rates: `CPIAUCSL`, `CPILFESL`, `PCEPI`, `PCEPILFE`, `FEDFUNDS`, `DGS2`, `DGS10`
- financial conditions: `SP500`, `VIXCLS`, `NFCI`, `BAA10Y`, `T10Y2Y`
- tech/growth proxies: `NASDAQCOM`, `SP500`, rates, VIX
- manufacturing cycle: `IPMAN`, `INDPRO`, `MANEMP`, `AMTMNO`, `DGORDER`, `ICSA`
- consumer/demand: `RSAFS`, `PCE`, `UMCSENT`, `PAYEMS`, `UNRATE`
- quarter outlook: equity, rates, volatility, industrial, manufacturing, and labor proxies

## Safety

This does not allow unrestricted AI browsing. The AI receives structured data from approved app-side source builders/connectors. Search landing pages are labeled as source-discovery context only.
