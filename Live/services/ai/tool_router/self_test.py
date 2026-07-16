from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
from typing import Any


def _load_router_symbols_for_direct_file_run() -> dict[str, Any]:
    """
    Allow this file to be executed directly from the repo root:

        python ./Live/services/ai/tool_router/self_test.py

    Direct execution has no package context, so relative imports would normally fail.
    This creates a temporary isolated package whose __path__ points at this folder.
    It avoids depending on the parent services.ai package import path.
    """
    router_dir = Path(__file__).resolve().parent
    package_name = "_tool_router_self_test_runtime"

    if package_name not in sys.modules:
        package = types.ModuleType(package_name)
        package.__path__ = [str(router_dir)]  # type: ignore[attr-defined]
        sys.modules[package_name] = package

    context_builder = importlib.import_module(f"{package_name}.context_builder")
    evidence_schema = importlib.import_module(f"{package_name}.evidence_schema")
    research_plan = importlib.import_module(f"{package_name}.research_plan")
    source_policy = importlib.import_module(f"{package_name}.source_policy")
    tool_registry = importlib.import_module(f"{package_name}.tool_registry")

    return {
        "build_evidence_packet": context_builder.build_evidence_packet,
        "EvidenceRow": evidence_schema.EvidenceRow,
        "build_research_plan": research_plan.build_research_plan,
        "classify_source": source_policy.classify_source,
        "guardrail_summary": source_policy.guardrail_summary,
        "get_tool_registry_diagnostics": tool_registry.get_tool_registry_diagnostics,
    }


if __package__ in (None, ""):
    _symbols = _load_router_symbols_for_direct_file_run()
    build_evidence_packet = _symbols["build_evidence_packet"]
    EvidenceRow = _symbols["EvidenceRow"]
    build_research_plan = _symbols["build_research_plan"]
    classify_source = _symbols["classify_source"]
    guardrail_summary = _symbols["guardrail_summary"]
    get_tool_registry_diagnostics = _symbols["get_tool_registry_diagnostics"]
else:
    from .context_builder import build_evidence_packet
    from .evidence_schema import EvidenceRow
    from .research_plan import build_research_plan
    from .source_policy import classify_source, guardrail_summary
    from .tool_registry import get_tool_registry_diagnostics


def run_self_test() -> dict[str, object]:
    question = "Compare AMD revenue EPS CPI PCE unemployment wages over five years"
    plan = build_research_plan(question, third_party_context_allowed=True)

    source_families = {step.source_family for step in plan.steps}
    required = {"SEC", "FRED", "BLS", "BEA"}
    missing = sorted(required - source_families)
    if missing:
        raise AssertionError(f"Plan missing expected official sources: {missing}")

    fred_policy = classify_source("FRED")
    news_policy = classify_source("Reuters")
    if not fred_policy.can_supply_numeric_facts:
        raise AssertionError("FRED should be allowed to supply numeric facts.")
    if news_policy.can_override_official:
        raise AssertionError("Third-party context should not override official facts.")

    row = EvidenceRow(
        source_family="FRED",
        source_quality="official_authoritative",
        evidence_type="macro_timeseries",
        title="CPIAUCSL sample row",
        url="https://fred.stlouisfed.org/series/CPIAUCSL",
        confidence="sample",
        values={
            "series_id": "CPIAUCSL",
            "latest_value": 333.979,
            "latest_date": "2026-05-01",
            "unit": "Index 1982-1984=100",
        },
    )
    packet = build_evidence_packet(question, plan=plan, rows=[row])
    if not packet.chart_ready_data:
        raise AssertionError("Expected chart-ready data from sample row.")
    if "Official data rows override" not in packet.markdown_summary:
        raise AssertionError("Expected guardrail summary in markdown summary.")

    registry = get_tool_registry_diagnostics()
    if not registry.tools:
        raise AssertionError("Expected tool registry diagnostics.")

    return {
        "status": "PASS",
        "planned_sources": sorted(source_families),
        "tool_count": len(registry.tools),
        "chart_ready_rows": len(packet.chart_ready_data),
        "guardrails": guardrail_summary().splitlines(),
    }


def main() -> int:
    result = run_self_test()
    print("AI Research Tool Router self-test: PASS")
    print(f"Planned sources: {', '.join(result['planned_sources'])}")
    print(f"Tool count: {result['tool_count']}")
    print(f"Chart-ready rows: {result['chart_ready_rows']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
