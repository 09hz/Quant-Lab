from __future__ import annotations

import py_compile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


LIVE_ROOT = Path(__file__).resolve().parents[1]
MODULE = LIVE_ROOT / "services" / "research" / "research_analyst_macro_anchors.py"
CALLBACKS = LIVE_ROOT / "services" / "ai" / "research_analyst_callbacks.py"


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"Missing {label}: {needle}")


def main() -> int:
    py_compile.compile(str(MODULE), doraise=True)
    py_compile.compile(str(CALLBACKS), doraise=True)

    module_text = MODULE.read_text(encoding="utf-8")
    callbacks_text = CALLBACKS.read_text(encoding="utf-8")

    for series_id in (
        "CPIAUCSL",
        "CPILFESL",
        "PCEPI",
        "PCEPILFE",
        "FEDFUNDS",
        "DGS2",
        "DGS10",
        "NASDAQCOM",
        "SP500",
        "VIXCLS",
        "IPMAN",
        "INDPRO",
        "AMTMNO",
        "DGORDER",
        "MANEMP",
        "RSAFS",
        "PAYEMS",
        "UNRATE",
    ):
        require(module_text, series_id, f"macro anchor series {series_id}")

    require(module_text, "change_1", "1-period trend delta")
    require(module_text, "change_3", "3-period trend delta")
    require(module_text, "change_6", "6-period trend delta")
    require(module_text, "build_macro_anchor_evidence", "macro anchor builder")
    require(module_text, "summarize_macro_anchor_coverage", "coverage summary helper")

    require(callbacks_text, "build_macro_anchor_evidence", "callback macro anchor import")
    require(callbacks_text, "macro_anchor_items", "callback macro anchor payload")
    require(callbacks_text, "macro_anchor_coverage", "callback macro coverage packet")
    require(callbacks_text, "mandatory_macro_anchors", "callback packet macro anchor metadata")
    require(callbacks_text, "Treat FRED structured macro anchors as confirmed official data", "prompt macro anchor instruction")
    require(callbacks_text, "search landing pages as discovery context only", "search landing page caution")

    from services.research.research_analyst_macro_anchors import (  # noqa: PLC0415
        build_macro_anchor_evidence,
        summarize_macro_anchor_coverage,
    )

    items, coverage, error = build_macro_anchor_evidence(
        question="market impact tech manufacturing current quarter",
        topic="inflation rates Fed",
        symbol="NVDA",
        selected_sources=["news"],
        max_items=8,
    )

    if not items:
        raise AssertionError("Expected at least a coverage summary item when FRED is not selected.")
    if coverage.get("fred_allowed") is not False:
        raise AssertionError("Expected fred_allowed=False when selected_sources excludes fred.")
    if not error:
        raise AssertionError("Expected warning when FRED is not selected.")
    summary = summarize_macro_anchor_coverage(coverage)
    if "Macro anchors loaded" not in summary:
        raise AssertionError("Coverage summary helper did not return expected text.")

    print("OK: Research Analyst mandatory macro anchors, trend deltas, and coverage wiring are applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
