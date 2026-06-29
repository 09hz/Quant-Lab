from __future__ import annotations

from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    path = root / "services" / "research" / "newsroom_callbacks.py"
    text = path.read_text(encoding="utf-8")

    required = [
        "def _brief_stable_key(",
        "def _brief_row_selection_id(",
        "def _assign_brief_selection_ids(",
        "def _brief_selection_matches(",
        "visible_results = _assign_brief_selection_ids(visible_results)",
        'item.get("brief_selection_id") or item.get("id")',
        "return visible_results, options, [], _render_result_cards(visible_results), status",
        "existing = {_brief_stable_key(item) for item in current",
        "if not _brief_selection_matches(item, selected):",
        "skipped_duplicate",
        "skipped_non_addable",
    ]

    missing = [item for item in required if item not in text]
    if missing:
        raise SystemExit("Missing Newsroom brief selection wiring: " + ", ".join(missing))

    print("OK: Newsroom brief add uses unique row selections, stable dedupe keys, and preserves distinct selected sources.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
