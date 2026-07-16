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
        package_dir / "reindex_memory.py",
        package_dir / "symbol_hygiene.py",
        package_dir / "hypothesis_engine.py",
        package_dir / "storage.py",
    ]

    for path in required:
        if not path.exists():
            print(f"Missing {path}")
            return 2
        ast.parse(path.read_text(encoding="utf-8", errors="replace"))

    if str(live_root) not in sys.path:
        sys.path.insert(0, str(live_root))

    from services.ai.market_memory.ingest import ingest_text_packet
    from services.ai.market_memory.reindex_memory import reindex_market_memory
    from services.ai.market_memory.research_packet import build_research_packet
    from services.ai.market_memory.storage import MarketMemoryStore
    from services.ai.market_memory.symbol_hygiene import NOISE_SYMBOLS

    with tempfile.TemporaryDirectory(prefix="market_memory_reindex_test_", ignore_cleanup_errors=True) as tmp:
        fake_live = Path(tmp) / "Live"
        memory_dir = fake_live / "data" / "market_memory"
        memory_dir.mkdir(parents=True, exist_ok=True)

        store = MarketMemoryStore(memory_dir / "market_memory.sqlite", memory_dir / "evidence_ledger.jsonl")

        ingest_text_packet(
            store=store,
            source_type="auto_lab_walk_forward",
            source_path="manual://reindex_noise_test",
            title="Noisy reindex test",
            text="AI PASS ENV WARN SEND LIVE RSI BUY AMD NVDA TSM ASML SMH semiconductors AI infrastructure.",
            metadata={
                "symbols": ["AI", "PASS", "ENV", "AMD", "NVDA", "TSM", "ASML", "SMH"],
                "themes": ["AI infrastructure", "Semiconductors"],
            },
        )

        result = reindex_market_memory(fake_live, theme="AI infrastructure semiconductors", max_symbols=12)
        packet = build_research_packet(fake_live, theme="AI infrastructure semiconductors", max_symbols=12)
        suggested = set(packet.get("suggested_symbols", []))
        bad = suggested.intersection(NOISE_SYMBOLS)
        if bad:
            print(f"Noise symbols survived reindex: {bad}, packet={packet.get('suggested_symbols')}")
            return 3

        if "AMD" not in suggested or "NVDA" not in suggested:
            print(f"Expected AMD/NVDA after reindex, got {packet.get('suggested_symbols')}")
            return 4

        if result.get("hypotheses_rebuilt", 0) < 1:
            print(f"Expected rebuilt hypotheses, got {result}")
            return 5

    print("v23.1.2 Market Memory Reindex Cleanup self-test: PASS")
    print("Noise symbols are removed from rebuilt research packets.")
    print("Research/simulation only. No broker calls or trade execution were made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
