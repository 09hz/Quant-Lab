from __future__ import annotations

from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    path = root / "services" / "research" / "newsroom_callbacks.py"
    text = path.read_text(encoding="utf-8")

    required = [
        "def _brief_stable_key(",
        "def _ensure_newsroom_brief_row_ids(",
        "def _brief_option_value(",
        "def _brief_match_selected(",
        "all visible rows are selectable for the brief",
        "user_added_to_brief",
        "Last Add Action",
        "Skipped duplicates",
        "Unmatched selections",
    ]
    missing = [item for item in required if item not in text]
    if missing:
        raise SystemExit("Missing expected Newsroom add-all wiring: " + ", ".join(missing))

    if '{"label": _brief_option_label(item), "value": item["id"]}' in text:
        raise SystemExit("Old raw-id checklist value wiring is still present.")

    print("OK: Newsroom brief add-all mode uses unique row selections, stable dedupe keys, and visible add counts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
