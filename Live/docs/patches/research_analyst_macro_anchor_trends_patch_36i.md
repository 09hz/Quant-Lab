# Patch 36i - Research Analyst mandatory macro anchors and trend deltas

Adds structured macro anchor evidence for Newsroom Research Analyst questions that ask about market impact, sector impact, correlation, or bullish/bearish quarter outlook.

## Why

The Research Analyst could answer safely, but the evidence packet was still too small. It often contained yield/equity/manufacturing proxies while missing mandatory inflation and policy anchors such as CPI, core CPI, PCE, core PCE, and FEDFUNDS.

## Added

- `Live/services/research/research_analyst_macro_anchors.py`
- `Live/scripts/check_research_analyst_macro_anchor_trends.py`

## Behavior

For broad Research Analyst questions, the app now attempts to add structured FRED evidence before search/discovery links:

- Inflation: `CPIAUCSL`, `CPILFESL`, `PCEPI`, `PCEPILFE`
- Policy/rates: `FEDFUNDS`, `DGS2`, `DGS10`, `T10Y2Y`
- Market/risk: `SP500`, `NASDAQCOM`, `VIXCLS`, `NFCI`, `BAA10Y`
- Manufacturing: `IPMAN`, `INDPRO`, `AMTMNO`, `DGORDER`, `MANEMP`, `ICSA`
- Demand/labor: `RSAFS`, `PCE`, `PAYEMS`, `UNRATE`, `UMCSENT`

Each structured series item includes latest observation, prior observation, 1-period change, 3-period change, 6-period change, observation date, FRED source link, coverage category, and confirmed/proxy label.

## Safety

The AI prompt now explicitly says to use FRED structured macro anchors as confirmed official data when present, treat search landing pages as discovery context only, keep series separate, and avoid assigning a value to a series unless that exact series supplied it.
