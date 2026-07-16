from __future__ import annotations

import json
from pathlib import Path


def main() -> int:
    live_root = Path(__file__).resolve().parents[2]
    path = live_root / "data" / "autolab_payload" / "approved_structured_evidence_latest.json"
    print(f"Approved structured evidence latest exists: {path.exists()}")
    print(f"Path: {path}")
    if not path.exists():
        return 0

    payload = json.loads(path.read_text(encoding="utf-8"))
    cards = payload.get("cards", [])
    print(f"Card count: {len(cards)}")
    for idx, card in enumerate(cards, 1):
        metadata = card.get("metadata") or {}
        points = metadata.get("points") or []
        latest = points[0] if points else {}
        print(
            idx,
            metadata.get("ticker"),
            metadata.get("metric"),
            latest.get("value"),
            latest.get("unit"),
            latest.get("end"),
            latest.get("filed"),
            latest.get("accession"),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
