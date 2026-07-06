# Patch 28b — Newsroom Source Relevance Routing

Patch 28 generated links too broadly. This patch adds source relevance routing before generating Newsroom links.

For `inflation rate`, Fiscal Data and SEC EDGAR are now skipped unless the query is actually fiscal/company/filing related. FRED/BLS/BEA/Fed/News are routed more directly.

## Test

```powershell
python .\Live\scripts\check_newsroom_source_routing.py --query "inflation rate"
python .\Live\scripts\check_newsroom_source_routing.py --query "federal debt deficit interest expense"
python .\Live\scripts\check_newsroom_source_routing.py --query "MSFT 10-K inflation"
```

This is still a link/search layer. It does not give AI direct API access or unrestricted browsing.
