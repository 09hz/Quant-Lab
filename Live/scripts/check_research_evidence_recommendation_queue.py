from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from services.research.evidence_coverage import (
        analyze_evidence_coverage,
        build_recommended_evidence_sources,
        recommendations_to_options,
    )

    gap_list_only = [
        {
            "source": "Research Analyst",
            "kind": "quant-research-playbook",
            "title": "Missing evidence list",
            "summary": (
                "DGS2 DGS10 FEDFUNDS VIXCLS PAYEMS UNRATE UMCSENT CPIAUCSL "
                "CPILFESL PCEPI PCEPILFE IPMAN INDPRO DGORDER AMTMNO NVDA AMD "
                "MSFT current-quarter guidance are missing."
            ),
        }
    ]
    coverage = analyze_evidence_coverage(gap_list_only)
    assert coverage["present"] == [], coverage
    assert len(coverage["missing"]) >= 6, coverage

    coverage, recs = build_recommended_evidence_sources(gap_list_only)
    assert len(recs) >= 10, len(recs)
    assert any(rec["id"] == "rec-fred-dgs10" for rec in recs), "missing DGS10 recommendation"
    assert any(rec["id"] == "rec-fred-vixcls" for rec in recs), "missing VIXCLS recommendation"
    assert any(rec["id"] == "rec-fred-payems" for rec in recs), "missing PAYEMS recommendation"
    assert recommendations_to_options(recs), "missing checklist options"

    source_items = [
        {
            "source": "FRED",
            "kind": "official-data",
            "title": "FRED DGS10 - 10-Year Treasury Yield",
            "url": "https://fred.stlouisfed.org/series/DGS10",
            "summary": "Official 10Y Treasury yield source.",
        },
        {
            "source": "FRED",
            "kind": "official-data",
            "title": "FRED VIXCLS - CBOE Volatility Index",
            "url": "https://fred.stlouisfed.org/series/VIXCLS",
            "summary": "Official volatility source.",
        },
    ]
    coverage = analyze_evidence_coverage(source_items)
    assert "rates" in coverage["present_keys"], coverage
    assert "risk" in coverage["present_keys"], coverage

    approved = {
        "source": "FRED",
        "kind": "official-data-recommendation",
        "title": "FRED PAYEMS - Nonfarm Payrolls",
        "url": "https://fred.stlouisfed.org/series/PAYEMS",
        "summary": "Official labor source.",
        "approved_recommendation": True,
    }
    coverage = analyze_evidence_coverage([approved])
    assert "labor_sentiment" in coverage["present_keys"], coverage

    print("OK: Research Evidence Recommendation Queue uses strict source coverage and ignores AI missing-gap text.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
