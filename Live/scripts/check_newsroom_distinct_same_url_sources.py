from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    live_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(live_root))

    path = live_root / "services" / "research" / "newsroom_callbacks.py"
    text = path.read_text(encoding="utf-8")

    required = [
        "def _brief_dedupe_key",
        "Do NOT collapse different visible rows just because they share the same URL",
        "source, type, title, URL, and",
        "_clean_brief_key_part",
    ]
    missing = [item for item in required if item not in text]
    if missing:
        raise SystemExit("Missing expected dedupe patch markers: " + ", ".join(missing))

    from services.research.newsroom_callbacks import _brief_dedupe_key  # noqa: PLC0415

    live_data = {
        "id": "fred-cpiaucsl-data",
        "brief_selection_id": "row-1",
        "source": "FRED",
        "kind": "fred-data",
        "title": "CPIAUCSL: Consumer Price Index for All Urban Consumers",
        "url": "https://fred.stlouisfed.org/series/CPIAUCSL",
        "summary": "Latest FRED value for CPIAUCSL: 333.979 on 2026-05-01.",
    }
    official_page = {
        "id": "fred-cpiaucsl-page",
        "brief_selection_id": "row-2",
        "source": "FRED",
        "kind": "official-series",
        "title": "FRED series: Consumer Price Index (CPIAUCSL)",
        "url": "https://fred.stlouisfed.org/series/CPIAUCSL",
        "summary": "Official series context for CPI.",
    }
    exact_duplicate = dict(live_data)
    exact_duplicate["brief_selection_id"] = "row-99"

    if _brief_dedupe_key(live_data) == _brief_dedupe_key(official_page):
        raise SystemExit("Distinct FRED data/context rows with the same URL are still collapsing.")

    if _brief_dedupe_key(live_data) != _brief_dedupe_key(exact_duplicate):
        raise SystemExit("Exact duplicate source rows are no longer deduped.")

    print("OK: Newsroom brief dedupe allows distinct same-URL source cards and only skips exact duplicate rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
