from __future__ import annotations

from pathlib import Path
import json
import sys
import tempfile


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def main() -> int:
    repo_root = _repo_root()
    live_root = repo_root / "Live"
    if str(live_root) not in sys.path:
        sys.path.insert(0, str(live_root))

    from services.ai.market_memory.ingest import ingest_text_packet, seed_sample_memory
    from services.ai.market_memory.reports import build_snapshot, write_memory_reports
    from services.ai.market_memory.storage import MarketMemoryStore

    with tempfile.TemporaryDirectory(prefix="market_memory_self_test_", ignore_cleanup_errors=True) as tmp:
        tmp_path = Path(tmp)
        db_path = tmp_path / "market_memory.sqlite"
        ledger_path = tmp_path / "evidence_ledger.jsonl"
        store = MarketMemoryStore(db_path, ledger_path)

        sample = seed_sample_memory(store)
        if not sample.get("evidence_id"):
            print("Seed sample did not return evidence_id.")
            return 2

        packet = ingest_text_packet(
            store=store,
            source_type="manual_test",
            source_path="manual://v23_self_test",
            title="Market memory self-test",
            text=(
                "AMD, NVDA, TSM and ASML are linked to semiconductors and AI infrastructure. "
                "Walk-forward validation should reject overfit strategy ideas before user handoff."
            ),
            metadata={"symbols": ["AMD", "NVDA", "TSM", "ASML"], "themes": ["AI infrastructure", "Semiconductors"]},
        )

        counts = store.summary_counts()
        if counts["evidence_items"] < 2:
            print(f"Expected at least 2 evidence items, got {counts}")
            return 3
        if counts["entities"] < 4:
            print(f"Expected at least 4 entities, got {counts}")
            return 4
        if counts["relationships"] < 4:
            print(f"Expected at least 4 relationships, got {counts}")
            return 5

        snapshot = build_snapshot(store)
        if not snapshot.get("top_relationships"):
            print("Snapshot missing relationships.")
            return 6

    # Also test real Live/data report path with the persistent store.
    from services.ai.market_memory.ingest import ingest_latest_artifacts

    result = ingest_latest_artifacts(live_root, limit=10, seed_sample=True)
    reports = write_memory_reports(live_root)

    required_reports = [
        "snapshot_path",
        "market_report_path",
        "entity_report_path",
        "relationship_report_path",
        "hypothesis_report_path",
    ]
    for key in required_reports:
        path = Path(reports[key])
        if not path.exists() or path.stat().st_size == 0:
            print(f"Missing/empty report: {key} -> {path}")
            return 7

    market_report = Path(reports["market_report_path"]).read_text(encoding="utf-8", errors="replace")
    if "Market Memory Report" not in market_report:
        print("Market report content check failed.")
        return 8

    print("v23.0 Market Memory Ledger self-test: PASS")
    print(f"real_store_counts: {result.get('counts')}")
    print(f"market_report_path: {reports['market_report_path']}")
    print(f"relationship_report_path: {reports['relationship_report_path']}")
    print(f"db_path: {reports['db_path']}")
    print("Research/simulation only. No broker calls or trade execution were made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
