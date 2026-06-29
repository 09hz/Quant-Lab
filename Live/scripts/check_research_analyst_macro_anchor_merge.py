from __future__ import annotations

from pathlib import Path
import py_compile
import sys


ROOT = Path(__file__).resolve().parents[1]
CALLBACKS = ROOT / "services" / "ai" / "research_analyst_callbacks.py"


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"Missing {label}: {needle}")


def main() -> int:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    py_compile.compile(str(CALLBACKS), doraise=True)
    text = CALLBACKS.read_text(encoding="utf-8")

    require(text, "macro_anchor_items,", "macro anchors included in _merge_newsroom_payloads")
    require(text, "max_items=40", "expanded evidence-packet item limit")
    require(text, "Include mandatory macro anchors directly in the evidence packet", "merge rationale comment")
    require(text, "evidence_packet_to_markdown", "evidence packet markdown flow remains wired")

    merge_idx = text.find("combined_payload = _merge_newsroom_payloads(")
    anchor_idx = text.find("macro_anchor_items,", merge_idx)
    brief_idx = text.find("brief_items,", merge_idx)
    if merge_idx < 0 or anchor_idx < 0 or brief_idx < 0 or not (merge_idx < anchor_idx < brief_idx):
        raise AssertionError("macro_anchor_items must be merged before brief_items so mandatory anchors are visible to the AI.")

    print("OK: Research Analyst macro anchors are merged into the evidence packet before brief/results/supplemental items.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
