
from __future__ import annotations

import csv
import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class OfficialSourceCandidate:
    source: str
    title: str
    url: str
    kind: str
    score: int = 100
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "title": self.title,
            "url": self.url,
            "kind": self.kind,
            "score": self.score,
            "note": self.note,
        }


SEC_TICKER_CACHE_URL = "https://www.sec.gov/files/company_tickers.json"


def _http_json(url: str, *, user_agent: str = "AlgoTrader Research contact@example.com") -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": user_agent, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _upper(value: str) -> str:
    return str(value or "").strip().upper()


def resolve_sec_company_sources(symbol: str, *, user_agent: str = "AlgoTrader Research contact@example.com") -> list[OfficialSourceCandidate]:
    symbol = _upper(symbol)
    if not symbol:
        return []

    data = _http_json(SEC_TICKER_CACHE_URL, user_agent=user_agent)
    match = None
    for row in data.values() if isinstance(data, dict) else []:
        if _upper(row.get("ticker")) == symbol:
            match = row
            break

    if not match:
        return [OfficialSourceCandidate("SEC EDGAR", f"SEC ticker mapping for {symbol}", SEC_TICKER_CACHE_URL, "sec-ticker-map", 80, "Official SEC ticker map; symbol not found.")]

    cik = str(match.get("cik_str") or "").zfill(10)
    company = str(match.get("title") or symbol)
    compact_cik = str(int(cik)) if cik.isdigit() else cik

    return [
        OfficialSourceCandidate("SEC EDGAR", f"SEC submissions JSON for {company} ({symbol})", f"https://data.sec.gov/submissions/CIK{cik}.json", "sec-submissions-json", 100, "Official SEC submissions endpoint."),
        OfficialSourceCandidate("SEC EDGAR", f"SEC companyfacts JSON for {company} ({symbol})", f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json", "sec-companyfacts-json", 100, "Official SEC extracted XBRL endpoint."),
        OfficialSourceCandidate("SEC EDGAR", f"SEC company browse page for {company} ({symbol})", f"https://www.sec.gov/edgar/browse/?CIK={compact_cik}", "sec-company-filings-page", 90, "Specific company page; prefer accession detail URLs after fetching filings."),
    ]


BLS_SERIES_HINTS = {
    "cpi": ["CUUR0000SA0", "CUSR0000SA0"],
    "inflation": ["CUUR0000SA0", "CUSR0000SA0"],
    "unemployment": ["LNS14000000"],
    "payrolls": ["CES0000000001"],
    "jobs": ["CES0000000001", "LNS14000000"],
    "wages": ["CES0500000003"],
    "ppi": ["WPUFD4"],
}


def resolve_bls_sources(query: str, *, start_year: int = 2020, end_year: int | None = None) -> list[OfficialSourceCandidate]:
    end_year = int(end_year or date.today().year)
    q = str(query or "").lower()
    series_ids: list[str] = []
    for key, ids in BLS_SERIES_HINTS.items():
        if key in q:
            series_ids.extend(ids)

    seen: set[str] = set()
    series_ids = [x for x in series_ids if not (x in seen or seen.add(x))]

    candidates: list[OfficialSourceCandidate] = []
    for sid in series_ids:
        url = "https://api.bls.gov/publicAPI/v2/timeseries/data/" + urllib.parse.quote(sid) + "?" + urllib.parse.urlencode({"startyear": str(start_year), "endyear": str(end_year)})
        candidates.append(OfficialSourceCandidate("BLS", f"BLS time-series API: {sid}", url, "bls-series-api", 100, "Specific BLS series API URL."))
    return candidates


BEA_DATASET_HINTS = {
    "gdp": {"dataset": "NIPA", "table": "T10101", "line": "1", "frequency": "Q"},
    "pce": {"dataset": "NIPA", "table": "T20804", "line": "1", "frequency": "M"},
    "personal consumption": {"dataset": "NIPA", "table": "T20804", "line": "1", "frequency": "M"},
    "corporate profits": {"dataset": "NIPA", "table": "T11200", "line": "15", "frequency": "Q"},
}


def resolve_bea_sources(query: str, *, user_id: str = "YOUR_BEA_API_KEY", year: str = "X") -> list[OfficialSourceCandidate]:
    q = str(query or "").lower()
    candidates: list[OfficialSourceCandidate] = []
    for key, spec in BEA_DATASET_HINTS.items():
        if key in q:
            params = {
                "UserID": user_id,
                "method": "GetData",
                "datasetname": spec["dataset"],
                "TableName": spec["table"],
                "LineNumber": spec["line"],
                "Frequency": spec["frequency"],
                "Year": year,
                "ResultFormat": "JSON",
            }
            url = "https://apps.bea.gov/api/data?" + urllib.parse.urlencode(params)
            candidates.append(OfficialSourceCandidate("BEA", f"BEA API {spec['dataset']} {spec['table']} line {spec['line']}", url, "bea-api", 90 if user_id != "YOUR_BEA_API_KEY" else 75, "Specific BEA API URL. Configure BEA_API_KEY for live retrieval."))
    return candidates


def resolve_treasury_sources(query: str) -> list[OfficialSourceCandidate]:
    q = str(query or "").lower()
    candidates: list[OfficialSourceCandidate] = []
    if "debt" in q:
        url = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/debt_to_penny?" + urllib.parse.urlencode({"sort": "-record_date", "page[size]": "25"})
        candidates.append(OfficialSourceCandidate("Treasury", "Treasury FiscalData debt to the penny API", url, "treasury-fiscaldata-api", 100, "Specific Treasury FiscalData endpoint."))
    if "rate" in q or "yield" in q:
        url = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/avg_interest_rates?" + urllib.parse.urlencode({"sort": "-record_date", "page[size]": "25"})
        candidates.append(OfficialSourceCandidate("Treasury", "Treasury FiscalData average interest rates API", url, "treasury-fiscaldata-api", 95, "Specific Treasury FiscalData endpoint. Use FRED DGS series for market yield curve history."))
    return candidates


FED_LINKS = {
    "fomc": "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
    "minutes": "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
    "h15": "https://www.federalreserve.gov/datadownload/Choose.aspx?rel=H15",
    "h.15": "https://www.federalreserve.gov/datadownload/Choose.aspx?rel=H15",
    "industrial production": "https://www.federalreserve.gov/releases/g17/current/",
    "g17": "https://www.federalreserve.gov/releases/g17/current/",
}


def resolve_federal_reserve_sources(query: str) -> list[OfficialSourceCandidate]:
    q = str(query or "").lower()
    out: list[OfficialSourceCandidate] = []
    for key, url in FED_LINKS.items():
        if key in q:
            out.append(OfficialSourceCandidate("Federal Reserve", f"Federal Reserve specific source for {key}", url, "federal-reserve-specific-page", 85, "Specific Fed release/calendar/data-download page, not generic search."))
    return out


def resolve_official_sources(query: str, *, symbols: list[str] | None = None, bea_api_key: str = "YOUR_BEA_API_KEY") -> list[OfficialSourceCandidate]:
    out: list[OfficialSourceCandidate] = []
    for symbol in symbols or []:
        try:
            out.extend(resolve_sec_company_sources(symbol))
        except Exception as exc:
            out.append(OfficialSourceCandidate("SEC EDGAR", f"SEC resolver failed for {symbol}", SEC_TICKER_CACHE_URL, "resolver-error", 50, str(exc)))
    out.extend(resolve_bls_sources(query))
    out.extend(resolve_bea_sources(query, user_id=bea_api_key))
    out.extend(resolve_treasury_sources(query))
    out.extend(resolve_federal_reserve_sources(query))
    return out


def write_candidates_csv(path: Path, candidates: list[OfficialSourceCandidate]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["source", "title", "url", "kind", "score", "note"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for candidate in candidates:
            writer.writerow(candidate.as_dict())
