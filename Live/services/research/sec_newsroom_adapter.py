from __future__ import annotations

import os
import re
import time
from typing import Any

import requests

_SEC_TICKER_MAP_CACHE: dict[str, Any] = {"loaded_at": 0.0, "data": {}}

SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "AlgoTrader research prototype contact@example.com")
SEC_HEADERS = {"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate"}

METRIC_SPECS: list[dict[str, Any]] = [
    {
        "metric": "revenue",
        "concepts": [
            ("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax"),
            ("us-gaap", "Revenues"),
            ("us-gaap", "SalesRevenueNet"),
        ],
        "units": ["USD"],
    },
    {"metric": "net_income", "concepts": [("us-gaap", "NetIncomeLoss")], "units": ["USD"]},
    {"metric": "eps", "concepts": [("us-gaap", "EarningsPerShareDiluted")], "units": ["USD/shares", "USD"]},
    {"metric": "operating_income", "concepts": [("us-gaap", "OperatingIncomeLoss")], "units": ["USD"]},
    {
        "metric": "cash",
        "concepts": [
            ("us-gaap", "CashAndCashEquivalentsAtCarryingValue"),
            ("us-gaap", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"),
        ],
        "units": ["USD"],
    },
    {"metric": "shares", "concepts": [("dei", "EntityCommonStockSharesOutstanding")], "units": ["shares"]},
]


def _extract_ticker(topic: str) -> str:
    text = str(topic or "").upper()
    stop = {"THE", "AND", "FOR", "SEC", "EDGAR", "FRED", "EARNINGS", "NEWS", "STOCK"}
    for token in re.findall(r"\b[A-Z]{1,6}\b", text):
        if token not in stop:
            return token
    return ""


def _ticker_map() -> dict[str, dict[str, Any]]:
    now = time.time()
    if _SEC_TICKER_MAP_CACHE["data"] and now - float(_SEC_TICKER_MAP_CACHE["loaded_at"]) < 86400:
        return _SEC_TICKER_MAP_CACHE["data"]

    response = requests.get("https://www.sec.gov/files/company_tickers.json", headers=SEC_HEADERS, timeout=20)
    response.raise_for_status()
    raw = response.json()

    mapped: dict[str, dict[str, Any]] = {}
    rows = raw.values() if isinstance(raw, dict) else raw or []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").upper().strip()
        cik = row.get("cik_str")
        title = str(row.get("title") or "").strip()
        if ticker and cik:
            mapped[ticker] = {
                "ticker": ticker,
                "cik": int(cik),
                "cik_padded": str(int(cik)).zfill(10),
                "title": title,
            }

    _SEC_TICKER_MAP_CACHE["data"] = mapped
    _SEC_TICKER_MAP_CACHE["loaded_at"] = now
    return mapped


def _companyfacts_for_ticker(ticker: str) -> tuple[dict[str, Any], dict[str, Any]]:
    ticker = str(ticker or "").upper().strip()
    row = _ticker_map().get(ticker)
    if not row:
        raise ValueError(f"Ticker not found in SEC ticker map: {ticker}")

    cik_padded = row["cik_padded"]
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json"
    response = requests.get(url, headers=SEC_HEADERS, timeout=30)
    response.raise_for_status()
    return row, response.json()


def _latest_fact(companyfacts: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any] | None:
    """
    Scan every candidate concept and unit, then choose the newest filed/end/accession.
    This prevents stale revenue concepts from beating newer revenue concepts.
    """
    facts = companyfacts.get("facts") if isinstance(companyfacts, dict) else {}
    if not isinstance(facts, dict):
        return None

    candidates: list[dict[str, Any]] = []

    for taxonomy, concept in spec["concepts"]:
        concept_obj = facts.get(taxonomy, {}).get(concept, {})
        units = concept_obj.get("units", {}) if isinstance(concept_obj, dict) else {}
        if not isinstance(units, dict):
            continue

        preferred_units = list(spec.get("units") or []) + list(units.keys())
        seen_units: set[str] = set()

        for unit in preferred_units:
            if unit in seen_units:
                continue
            seen_units.add(unit)

            entries = units.get(unit)
            if not isinstance(entries, list):
                continue

            for entry in entries:
                if not isinstance(entry, dict) or entry.get("val") is None:
                    continue

                form = str(entry.get("form") or "")
                if form and form not in {"10-Q", "10-K", "20-F", "40-F"}:
                    continue

                candidates.append(
                    {
                        "taxonomy": taxonomy,
                        "concept": concept,
                        "label": concept_obj.get("label") or concept,
                        "unit": unit,
                        "value": entry.get("val"),
                        "period_end": entry.get("end") or "",
                        "start": entry.get("start") or "",
                        "filed": entry.get("filed") or "",
                        "form": entry.get("form") or "",
                        "accession": entry.get("accn") or "",
                        "fy": entry.get("fy") or "",
                        "fp": entry.get("fp") or "",
                        "frame": entry.get("frame") or "",
                    }
                )

    if not candidates:
        return None

    def sort_key(entry: dict[str, Any]) -> tuple[str, str, str, int]:
        form_rank = 1 if str(entry.get("form") or "") in {"10-Q", "10-K", "20-F", "40-F"} else 0
        return (
            str(entry.get("filed") or ""),
            str(entry.get("period_end") or ""),
            str(entry.get("accession") or ""),
            form_rank,
        )

    candidates.sort(key=sort_key, reverse=True)
    return candidates[0]


def _filing_index_url(cik: int, accession: str) -> str:
    accession = str(accession or "").strip()
    if not accession:
        return f"https://www.sec.gov/edgar/browse/?CIK={int(cik)}"
    accession_nodash = accession.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_nodash}/{accession}-index.html"


def build_sec_companyfacts_newsroom_items(topic: str, sources: list[str] | None = None, limit: int = 12) -> list[dict[str, Any]]:
    ticker = _extract_ticker(topic)
    if not ticker:
        return []

    ticker_row, companyfacts = _companyfacts_for_ticker(ticker)
    entity = str(companyfacts.get("entityName") or ticker_row.get("title") or ticker)
    cik = int(companyfacts.get("cik") or ticker_row.get("cik") or 0)
    cik_padded = str(cik).zfill(10)
    companyfacts_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json"

    items: list[dict[str, Any]] = []
    for spec in METRIC_SPECS:
        fact = _latest_fact(companyfacts, spec)
        if not fact:
            continue

        metric = spec["metric"]
        concept = fact["concept"]
        period_end = fact["period_end"]
        accession = fact["accession"]
        item_id = f"sec-companyfacts:{ticker}:{metric}:{concept}:{period_end}:{accession}"
        filing_url = _filing_index_url(cik, accession)

        metadata = {
            "ticker": ticker,
            "symbol": ticker,
            "company": entity,
            "entity": entity,
            "entityName": entity,
            "cik": cik,
            "metric": metric,
            "label": fact["label"],
            "concept": concept,
            "taxonomy": fact["taxonomy"],
            "latest_value": fact["value"],
            "value": fact["value"],
            "latest_unit": fact["unit"],
            "unit": fact["unit"],
            "period_end": period_end,
            "filed": fact["filed"],
            "filed_date": fact["filed"],
            "form": fact["form"],
            "accession": accession,
            "accn": accession,
            "fy": fact["fy"],
            "fp": fact["fp"],
            "frame": fact["frame"],
            "source_url": companyfacts_url,
            "companyfacts_url": companyfacts_url,
            "filing_url": filing_url,
            "evidence_role": "confirmed-official-sec-companyfacts",
            "path": "normal Newsroom checkbox/Add Selected to Brief",
            "needs_manual_search": False,
        }

        summary = (
            "SEC companyfacts official-data card. "
            f"{entity} ({ticker}) {metric}: {fact['value']} {fact['unit']} "
            f"| period end {period_end} | filed {fact['filed']} | {fact['form']} "
            f"| accession {accession} | concept {concept}. "
            "Path: normal Newsroom checkbox/Add Selected to Brief."
        )

        item = {
            "id": item_id,
            "brief_selection_id": item_id,
            "brief_dedupe_key": item_id,
            "title": f"{entity} ({ticker}) {metric} from SEC companyfacts",
            "summary": summary,
            "url": filing_url,
            "source": "SEC EDGAR companyfacts",
            "kind": "sec-companyfacts-official-data-card",
            "confidence": "high",
            "selectable": True,
            "needs_manual_search": False,
            "source_type": "official",
            "evidence_role": "confirmed-official-sec-companyfacts",
            "metadata": metadata,
        }
        item.update(metadata)
        items.append(item)

    return items[:limit]


def _is_noisy_sec_discovery_item(item: dict[str, Any], ticker: str) -> bool:
    url = str(item.get("url") or item.get("source_url") or "").lower()
    title = str(item.get("title") or item.get("headline") or "").lower()
    summary = str(item.get("summary") or "").lower()
    kind = str(item.get("kind") or "").lower()
    source = str(item.get("source") or "").lower()

    if "sec-companyfacts-official-data-card" in kind:
        return False

    if "data.sec.gov/api/xbrl/companyfacts" in url:
        return True
    if "companyfacts" in title and ("{" in summary or '"facts"' in summary or "entitycommonstocksharesoutstanding" in summary):
        return True
    if "sec.gov/edgar/search" in url:
        return True
    if "sec edgar company search" in title:
        return True
    if kind in {"sec-edgar-search", "sec-search", "sec-company-search"}:
        return True
    if ticker and ticker.lower() in title and "sec" in source and "search" in title:
        return True

    return False


def extend_results_with_sec_companyfacts(topic: str, sources: list[str] | None, results: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    source_text = " ".join(str(s).lower() for s in (sources or []))
    topic_text = str(topic or "").lower()
    sec_requested = (
        not sources
        or "sec" in source_text
        or "edgar" in source_text
        or "companyfacts" in source_text
        or "sec" in topic_text
        or "edgar" in topic_text
        or "earnings" in topic_text
    )
    if not sec_requested:
        return list(results or [])

    ticker = _extract_ticker(topic)

    try:
        metric_items = build_sec_companyfacts_newsroom_items(topic, sources=sources)
    except Exception as exc:
        error_id = f"sec-companyfacts-error:{ticker or 'unknown'}"
        return [
            {
                "id": error_id,
                "brief_selection_id": error_id,
                "title": f"SEC companyfacts metric extraction failed for {ticker or topic}",
                "summary": str(exc),
                "url": "",
                "source": "SEC EDGAR companyfacts",
                "kind": "sec-companyfacts-error",
                "confidence": "low",
                "selectable": False,
                "needs_manual_search": True,
                "metadata": {"ticker": ticker, "error": str(exc)},
            },
            *list(results or []),
        ]

    filtered_existing: list[dict[str, Any]] = []
    for item in results or []:
        if not isinstance(item, dict):
            continue
        if metric_items and _is_noisy_sec_discovery_item(item, ticker):
            continue
        filtered_existing.append(item)

    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for item in [*metric_items, *filtered_existing]:
        key = str(item.get("id") or item.get("brief_selection_id") or item.get("url") or item.get("title") or "")
        if key and key in seen:
            continue
        output.append(item)
        if key:
            seen.add(key)

    return output
