from __future__ import annotations

from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    path = root / "services" / "research" / "newsroom_callbacks.py"
    text = path.read_text(encoding="utf-8")

    required = [
        "every visible Newsroom row can be added to the brief",
        'item["brief_selection_id"] = f"visible-row-{idx}-{raw_id}"',
        'item["selectable"] = True',
        "No rail-guard dedupe here",
        "Skipped duplicates: 0",
        "Mode: user-controlled add-all",
    ]
    missing = [item for item in required if item not in text]
    if missing:
        raise SystemExit("Missing no-railguard selection wiring: " + ", ".join(missing))

    forbidden = [
        'existing = {item.get("id") for item in current}',
        'item.get("id") in selected and item.get("id") not in existing',
        'skipped_duplicates',
    ]
    bad = [item for item in forbidden if item in text]
    if bad:
        raise SystemExit("Old restrictive brief-add behavior still present: " + ", ".join(bad))

    print("OK: Newsroom brief add-all mode lets the user append every matched visible row.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
