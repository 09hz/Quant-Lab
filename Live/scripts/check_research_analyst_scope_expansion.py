from __future__ import annotations

import py_compile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SCOPE = ROOT / "services" / "research" / "research_analyst_scope.py"
GAP = ROOT / "services" / "research" / "research_analyst_gap_fill.py"
CALLBACKS = ROOT / "services" / "ai" / "research_analyst_callbacks.py"


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"Missing {label}: {needle}")


def main() -> int:
    for path in (SCOPE, GAP, CALLBACKS):
        if not path.exists():
            raise AssertionError(f"Missing expected file: {path}")
        py_compile.compile(str(path), doraise=True)

    callbacks = CALLBACKS.read_text(encoding="utf-8")
    require(callbacks, "build_structured_gap_fill_items", "structured gap-fill import/use")
    require(callbacks, "structured_items", "structured items merged before search links")
    require(callbacks, "source-discovery", "source-discovery guardrail")

    from services.research.research_analyst_scope import plan_research_scope
    from services.research.research_analyst_gap_fill import build_structured_gap_fill_items

    plan = plan_research_scope(
        question="How does inflation impact tech and manufacturing, and is the current quarter bullish or bearish?",
        topic="inflation rates Fed market conditions",
        symbol="NVDA",
        max_series=24,
    )
    series_ids = {item["series_id"] for item in plan["series"]}
    for required in ("CPIAUCSL", "PCEPILFE", "FEDFUNDS", "NASDAQCOM", "IPMAN", "AMTMNO", "VIXCLS"):
        if required not in series_ids:
            raise AssertionError(f"Scope planner did not include expected series: {required}")

    items, packet, error = build_structured_gap_fill_items(
        question="How does inflation impact tech and manufacturing, and is the current quarter bullish or bearish?",
        topic="inflation rates Fed market conditions",
        symbol="NVDA",
        selected_sources=["fred", "fed", "news"],
        max_items=8,
        fetch_live=False,
    )
    if not items:
        raise AssertionError("Structured gap-fill produced no offline source-discovery items.")
    if not any(item.get("source_role") == "source-discovery" for item in items):
        raise AssertionError("Offline structured gap-fill should label no-data items as source-discovery.")
    if "scopes" not in packet:
        raise AssertionError("Structured gap-fill did not return a scope plan.")

    print("OK: Research Analyst structured scope expansion is wired for tech, manufacturing, financial conditions, and quarter outlook.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
