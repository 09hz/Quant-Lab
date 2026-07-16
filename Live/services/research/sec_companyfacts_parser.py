from __future__ import annotations

import argparse
import csv
import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SEC_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"

COMMON_FACTS = {
    # Revenue concept names vary by filer and era. AMD's current filings often
    # use RevenueFromContractWithCustomerExcludingAssessedTax, while older data
    # may use Revenues or SalesRevenueNet.
    "revenue": [
        ("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax"),
        ("us-gaap", "Revenues"),
        ("us-gaap", "SalesRevenueNet"),
        ("us-gaap", "SalesRevenueGoodsNet"),
        ("us-gaap", "SalesRevenueServicesNet"),
    ],
    "net_income": [
        ("us-gaap", "NetIncomeLoss"),
        ("us-gaap", "ProfitLoss"),
    ],
    "eps": [
        ("us-gaap", "EarningsPerShareDiluted"),
        ("us-gaap", "EarningsPerShareBasic"),
    ],
    "operating_income": [
        ("us-gaap", "OperatingIncomeLoss"),
    ],
    "gross_profit": [
        ("us-gaap", "GrossProfit"),
    ],
    "cash": [
        ("us-gaap", "CashAndCashEquivalentsAtCarryingValue"),
        ("us-gaap", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"),
        ("us-gaap", "CashAndCashEquivalentsFairValueDisclosure"),
    ],
    "assets": [
        ("us-gaap", "Assets"),
    ],
    "liabilities": [
        ("us-gaap", "Liabilities"),
    ],
    "shares": [
        ("dei", "EntityCommonStockSharesOutstanding"),
        ("dei", "EntityPublicFloat"),
    ],
}


@dataclass(frozen=True)
class SecFactPoint:
    ticker: str
    cik: str
    entity_name: str
    metric: str
    taxonomy: str
    concept: str
    unit: str
    end: str
    value: float | int | str
    form: str
    filed: str
    fiscal_year: int | str
    fiscal_period: str
    accession: str

    def as_dict(self) -> dict[str, Any]:
        accn_clean = str(self.accession or "").replace("-", "")
        filing_url = ""
        if self.cik and accn_clean:
            filing_url = f"https://www.sec.gov/Archives/edgar/data/{int(self.cik)}/{accn_clean}/"
        return {
            "ticker": self.ticker,
            "cik": self.cik,
            "entity_name": self.entity_name,
            "metric": self.metric,
            "taxonomy": self.taxonomy,
            "concept": self.concept,
            "unit": self.unit,
            "end": self.end,
            "value": self.value,
            "form": self.form,
            "filed": self.filed,
            "fiscal_year": self.fiscal_year,
            "fiscal_period": self.fiscal_period,
            "accession": self.accession,
            "filing_url": filing_url,
            "source_url": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{str(self.cik).zfill(10)}.json",
        }


def _http_json(url: str, *, user_agent: str) -> Any:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        return json.loads(resp.read().decode("utf-8"))


def resolve_ticker_to_cik(ticker: str, *, user_agent: str) -> tuple[str, str]:
    ticker = str(ticker or "").strip().upper()
    data = _http_json(SEC_TICKER_MAP_URL, user_agent=user_agent)
    for row in data.values() if isinstance(data, dict) else []:
        if str(row.get("ticker") or "").strip().upper() == ticker:
            cik = str(row.get("cik_str") or "").zfill(10)
            name = str(row.get("title") or ticker)
            return cik, name
    raise RuntimeError(f"SEC ticker map did not contain ticker: {ticker}")


def fetch_companyfacts(ticker: str, *, user_agent: str) -> dict[str, Any]:
    cik, _name = resolve_ticker_to_cik(ticker, user_agent=user_agent)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    return _http_json(url, user_agent=user_agent)


def _concept_units(payload: dict[str, Any], taxonomy: str, concept: str) -> dict[str, list[dict[str, Any]]]:
    try:
        return payload["facts"][taxonomy][concept]["units"]
    except Exception:
        return {}


def extract_recent_fact_points(
    payload: dict[str, Any],
    *,
    ticker: str,
    metric: str,
    limit: int = 8,
    forms: set[str] | None = None,
) -> list[SecFactPoint]:
    forms = forms or {"10-K", "10-Q"}
    cik = str(payload.get("cik") or "").zfill(10)
    entity = str(payload.get("entityName") or ticker)

    concept_specs = COMMON_FACTS.get(metric, [])
    points: list[SecFactPoint] = []

    for taxonomy, concept in concept_specs:
        units = _concept_units(payload, taxonomy, concept)
        for unit, rows in units.items():
            for row in rows or []:
                form = str(row.get("form") or "")
                if form not in forms:
                    continue
                if row.get("val") is None:
                    continue
                points.append(
                    SecFactPoint(
                        ticker=ticker.upper(),
                        cik=cik,
                        entity_name=entity,
                        metric=metric,
                        taxonomy=taxonomy,
                        concept=concept,
                        unit=str(unit),
                        end=str(row.get("end") or ""),
                        value=row.get("val"),
                        form=form,
                        filed=str(row.get("filed") or ""),
                        fiscal_year=row.get("fy") or "",
                        fiscal_period=str(row.get("fp") or ""),
                        accession=str(row.get("accn") or ""),
                    )
                )

    # Prefer most recent filed/end date across all accepted concepts. This prevents
    # a stale legacy concept such as old "Revenues" from beating a newer current
    # filer-specific revenue concept.
    seen: set[tuple[str, str, str, str]] = set()
    unique: list[SecFactPoint] = []
    for p in sorted(points, key=lambda x: (str(x.filed or ""), str(x.end or ""), str(x.fiscal_year or ""), str(x.fiscal_period or "")), reverse=True):
        key = (p.accession, p.concept, p.unit, p.end)
        if key in seen:
            continue
        seen.add(key)
        unique.append(p)

    return unique[:limit]


def build_sec_evidence_cards(
    ticker: str,
    *,
    metrics: list[str] | None = None,
    user_agent: str,
    limit_per_metric: int = 6,
) -> list[dict[str, Any]]:
    metrics = metrics or ["revenue", "net_income", "eps", "operating_income", "cash", "shares"]
    payload = fetch_companyfacts(ticker, user_agent=user_agent)

    cards: list[dict[str, Any]] = []
    for metric in metrics:
        points = extract_recent_fact_points(payload, ticker=ticker, metric=metric, limit=limit_per_metric)
        if not points:
            continue

        latest = points[0]
        cards.append(
            {
                "kind": "sec-companyfacts-official-data",
                "source": "SEC EDGAR",
                "title": f"{latest.entity_name} ({ticker.upper()}) {metric} from SEC companyfacts",
                "summary": (
                    f"Latest {metric}: {latest.value} {latest.unit} for period ending {latest.end}; "
                    f"form {latest.form}, filed {latest.filed}, accession {latest.accession}."
                ),
                "url": latest.as_dict()["source_url"],
                "source_url": latest.as_dict()["source_url"],
                "filing_url": latest.as_dict()["filing_url"],
                "metadata": {
                    "ticker": ticker.upper(),
                    "cik": latest.cik,
                    "entity_name": latest.entity_name,
                    "metric": metric,
                    "taxonomy": latest.taxonomy,
                    "concept": latest.concept,
                    "unit": latest.unit,
                    "official": True,
                    "structured": True,
                    "points": [p.as_dict() for p in points],
                },
            }
        )

    return cards


def write_cards_json(path: Path, cards: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cards, indent=2, default=str) + "\n", encoding="utf-8")


def write_points_csv(path: Path, cards: list[dict[str, Any]]) -> None:
    rows: list[dict[str, Any]] = []
    for card in cards:
        rows.extend((card.get("metadata") or {}).get("points") or [])

    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    fields = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch and parse SEC companyfacts into Newsroom-ready evidence cards.")
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--metrics", default="revenue,net_income,eps,operating_income,cash,shares")
    parser.add_argument("--out-json", type=Path, default=Path("data/autolab_payload/sec_companyfacts_cards.json"))
    parser.add_argument("--out-csv", type=Path, default=Path("data/autolab_payload/sec_companyfacts_points.csv"))
    parser.add_argument("--user-agent", default="AlgoTrader Research contact@example.com")
    args = parser.parse_args()

    metrics = [x.strip() for x in args.metrics.split(",") if x.strip()]
    cards = build_sec_evidence_cards(args.ticker, metrics=metrics, user_agent=args.user_agent)
    write_cards_json(args.out_json, cards)
    write_points_csv(args.out_csv, cards)

    print(f"Wrote {len(cards)} SEC evidence card(s): {args.out_json}")
    print(f"Wrote SEC fact point CSV: {args.out_csv}")
    for card in cards:
        print(f"- {card['title']}")
        print(f"  {card['summary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
