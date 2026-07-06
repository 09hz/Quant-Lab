from __future__ import annotations

import importlib
import json
import sys
import tempfile
import types
from pathlib import Path
from typing import Any


def _load_router_symbols_for_direct_file_run() -> dict[str, Any]:
    router_dir = Path(__file__).resolve().parent
    package_name = "_tool_router_legacy_bridge_self_test_runtime"

    if package_name not in sys.modules:
        package = types.ModuleType(package_name)
        package.__path__ = [str(router_dir)]  # type: ignore[attr-defined]
        sys.modules[package_name] = package

    legacy_bridge = importlib.import_module(f"{package_name}.legacy_bridge")
    return {
        "build_router_packet_from_legacy_brief": legacy_bridge.build_router_packet_from_legacy_brief,
        "write_router_packet_diagnostics_from_legacy_brief": legacy_bridge.write_router_packet_diagnostics_from_legacy_brief,
    }


if __package__ in (None, ""):
    _symbols = _load_router_symbols_for_direct_file_run()
    build_router_packet_from_legacy_brief = _symbols["build_router_packet_from_legacy_brief"]
    write_router_packet_diagnostics_from_legacy_brief = _symbols["write_router_packet_diagnostics_from_legacy_brief"]
else:
    from .legacy_bridge import build_router_packet_from_legacy_brief, write_router_packet_diagnostics_from_legacy_brief


SAMPLE_BRIEF = [
    {
        "title": "ADVANCED MICRO DEVICES INC (AMD) revenue from SEC companyfacts",
        "source": "SEC EDGAR companyfacts",
        "kind": "sec-companyfacts",
        "confidence": "high",
        "url": "https://data.sec.gov/api/xbrl/companyfacts/CIK0000002488.json",
        "ticker": "AMD",
        "entity": "ADVANCED MICRO DEVICES INC",
        "metric": "revenue",
        "latest_value": 10253000000,
        "unit": "USD",
        "period_end": "2026-03-28",
        "filed": "2026-05-06",
        "form": "10-Q",
        "accession": "0000002488-26-000076",
        "concept": "RevenueFromContractWithCustomerExcludingAssessedTax",
        "cik": "2488",
    },
    {
        "title": "CPIAUCSL: Consumer Price Index for All Urban Consumers: All Items in U.S. City Average",
        "source": "FRED",
        "kind": "fred-data",
        "confidence": "high",
        "url": "https://fred.stlouisfed.org/series/CPIAUCSL",
        "summary": "Latest FRED value for CPIAUCSL: 333.979 on 2026-05-01 (Index 1982-1984=100, Monthly). Prior value: 332.407 on 2026-04-01; change vs prior: +1.572.",
    },
    {
        "title": "FRED series: Nonfarm Payrolls (PAYEMS)",
        "source": "FRED",
        "kind": "official-series",
        "confidence": "high",
        "url": "https://fred.stlouisfed.org/series/PAYEMS",
        "summary": "Employment trend context.",
    },
    {
        "title": "All Employees, Total Nonfarm",
        "source": "BLS",
        "kind": "bls-data",
        "confidence": "high",
        "url": "https://data.bls.gov/timeseries/CES0000000001",
        "summary": "Latest BLS value for CES0000000001: 158,984 on 2026-06-01 (Thousands of persons, Monthly). Prior value: 158,927 on 2026-05-01; change vs prior: +57.",
    },
]


def run_self_test() -> dict[str, Any]:
    question = "Compare AMD revenue with CPI and payrolls"
    packet = build_router_packet_from_legacy_brief(SAMPLE_BRIEF, question=question, include_bea_placeholder=True)

    source_counts = {source: len(rows) for source, rows in packet.rows_by_source().items()}
    for required in ("SEC", "FRED", "BLS", "BEA"):
        if required not in source_counts:
            raise AssertionError(f"Missing required source in packet: {required}")

    if not packet.chart_ready_data:
        raise AssertionError("Expected chart-ready rows from parsed FRED/BLS sample summaries.")

    fred_rows = [row for row in packet.rows if row.source_family == "FRED"]
    if not any(row.values.get("series_id") == "CPIAUCSL" and row.values.get("latest_value") == 333.979 for row in fred_rows):
        raise AssertionError("Expected parsed FRED CPIAUCSL numeric values.")

    bls_rows = [row for row in packet.rows if row.source_family == "BLS"]
    if not any(row.values.get("series_id") == "CES0000000001" and row.values.get("latest_value") == 158984 for row in bls_rows):
        raise AssertionError("Expected parsed BLS payroll numeric values.")

    with tempfile.TemporaryDirectory() as tmp:
        diagnostic_packet = write_router_packet_diagnostics_from_legacy_brief(
            SAMPLE_BRIEF,
            output_dir=tmp,
            question=question,
            include_bea_placeholder=True,
        )
        status_path = Path(tmp) / "router_last_legacy_bridge_status.json"
        if not status_path.exists():
            raise AssertionError("Expected status diagnostic JSON.")
        status = json.loads(status_path.read_text(encoding="utf-8"))
        if status.get("row_count") != len(diagnostic_packet.rows):
            raise AssertionError("Status row_count mismatch.")

    return {
        "status": "PASS",
        "row_count": len(packet.rows),
        "chart_ready_rows": len(packet.chart_ready_data),
        "source_counts": source_counts,
    }


def main() -> int:
    result = run_self_test()
    print("AI Research Tool Router legacy bridge self-test: PASS")
    print(f"Row count: {result['row_count']}")
    print(f"Chart-ready rows: {result['chart_ready_rows']}")
    print(f"Source counts: {json.dumps(result['source_counts'], sort_keys=True)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
