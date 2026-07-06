from __future__ import annotations

from pathlib import Path
import ast
import sys
import tempfile


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def main() -> int:
    repo_root = _repo_root()
    live_root = repo_root / "Live"
    package_dir = live_root / "services" / "ai" / "market_memory"

    required = [
        package_dir / "hypothesis_engine.py",
        package_dir / "research_packet.py",
        package_dir / "build_research_packet.py",
        package_dir / "ingest.py",
        package_dir / "reports.py",
        package_dir / "storage.py",
    ]

    for path in required:
        if not path.exists():
            print(f"Missing {path}")
            return 2
        ast.parse(path.read_text(encoding="utf-8", errors="replace"))

    if str(live_root) not in sys.path:
        sys.path.insert(0, str(live_root))

    from services.ai.market_memory.ingest import ingest_text_packet, ingest_latest_artifacts
    from services.ai.market_memory.reports import write_memory_reports
    from services.ai.market_memory.research_packet import write_research_packet
    from services.ai.market_memory.storage import MarketMemoryStore

    with tempfile.TemporaryDirectory(prefix="market_memory_v23_1_", ignore_cleanup_errors=True) as tmp:
        tmp_path = Path(tmp)
        store = MarketMemoryStore(tmp_path / "market_memory.sqlite", tmp_path / "evidence_ledger.jsonl")

        result = ingest_text_packet(
            store=store,
            source_type="auto_lab_walk_forward",
            source_path="manual://v23_1_self_test_walk_forward",
            title="v23.1 walk-forward RSI test",
            text=(
                "AMD NVDA TSM ASML AI infrastructure semiconductors. "
                "Strategy candidate: seed_rsi_mean_reversion_rsi_14_to_17. "
                "RSI buy when crossunder 30 and sell when crossover 70. "
                "walk_forward result partial_survival medium_overfit_warning test_score: 71.25."
            ),
            metadata={
                "symbols": ["AMD", "NVDA", "TSM", "ASML"],
                "themes": ["AI infrastructure", "Semiconductors"],
                "test_score": 71.25,
            },
        )

        counts = store.summary_counts()
        if counts["hypotheses"] < 1:
            print(f"Expected hypotheses after ingest, got {counts}")
            return 3
        if counts["strategy_memory"] < 1:
            print(f"Expected strategy memory after ingest, got {counts}")
            return 4
        if result.get("hypothesis_count", 0) < 1 or result.get("strategy_memory_count", 0) < 1:
            print(f"Expected result counts for hypothesis/strategy memory, got {result}")
            return 5

    real_result = ingest_latest_artifacts(live_root, limit=25, seed_sample=True)
    reports = write_memory_reports(live_root)
    packet_paths = write_research_packet(live_root, theme="AI infrastructure semiconductors", max_symbols=12)

    for key in ["market_report_path", "relationship_report_path", "hypothesis_report_path"]:
        path = Path(reports[key])
        if not path.exists() or path.stat().st_size == 0:
            print(f"Missing report {key}: {path}")
            return 6

    for key in ["markdown_path", "json_path"]:
        path = Path(packet_paths[key])
        if not path.exists() or path.stat().st_size == 0:
            print(f"Missing research packet {key}: {path}")
            return 7

    market_report_text = Path(reports["market_report_path"]).read_text(encoding="utf-8", errors="replace")
    if "Open / Active Hypotheses" not in market_report_text or "Strategy Memory" not in market_report_text:
        print("Market report missing v23.1 sections.")
        return 8

    print("v23.1 Market Memory Hypothesis Upgrade self-test: PASS")
    print(f"real_ingest_counts: {real_result.get('counts')}")
    print(f"research_packet_markdown: {packet_paths['markdown_path']}")
    print(f"research_packet_json: {packet_paths['json_path']}")
    print("Research/simulation only. No broker calls or trade execution were made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
