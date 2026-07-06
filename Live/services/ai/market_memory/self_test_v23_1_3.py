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
        package_dir / "theme_ranking.py",
        package_dir / "research_packet.py",
        package_dir / "storage.py",
        package_dir / "ingest.py",
    ]

    for path in required:
        if not path.exists():
            print(f"Missing {path}")
            return 2
        ast.parse(path.read_text(encoding="utf-8", errors="replace"))

    if str(live_root) not in sys.path:
        sys.path.insert(0, str(live_root))

    from services.ai.market_memory.ingest import ingest_text_packet
    from services.ai.market_memory.research_packet import build_research_packet, write_research_packet
    from services.ai.market_memory.storage import MarketMemoryStore

    with tempfile.TemporaryDirectory(prefix="market_memory_theme_rank_", ignore_cleanup_errors=True) as tmp:
        fake_live = Path(tmp) / "Live"
        memory_dir = fake_live / "data" / "market_memory"
        memory_dir.mkdir(parents=True, exist_ok=True)

        store = MarketMemoryStore(memory_dir / "market_memory.sqlite", memory_dir / "evidence_ledger.jsonl")

        ingest_text_packet(
            store=store,
            source_type="auto_lab_symbol_discovery",
            source_path="manual://consumer_packet",
            title="Consumer discretionary packet",
            text="TSLA GM F XLY consumer discretionary EV autos retail strategy research.",
            metadata={"symbols": ["TSLA", "GM", "F", "XLY"], "themes": ["Consumer discretionary"]},
        )

        ingest_text_packet(
            store=store,
            source_type="auto_lab_symbol_discovery",
            source_path="manual://semiconductor_packet",
            title="AI infrastructure semiconductor packet",
            text="AMD NVDA TSM ASML AVGO SMH SOXX semiconductors AI infrastructure GPU data center chips.",
            metadata={"symbols": ["AMD", "NVDA", "TSM", "ASML", "AVGO", "SMH", "SOXX"], "themes": ["AI infrastructure", "Semiconductors"]},
        )

        packet = build_research_packet(fake_live, theme="AI infrastructure semiconductors", max_symbols=8)
        suggested = packet.get("suggested_symbols", [])

        if "AMD" not in suggested or "NVDA" not in suggested:
            print(f"Expected AMD/NVDA in suggested symbols, got {suggested}")
            return 3

        if "AI" in suggested or "RSI" in suggested or "BUY" in suggested:
            print(f"Noise symbols survived in suggested symbols: {suggested}")
            return 4

        hypotheses = packet.get("hypotheses", [])
        if not hypotheses:
            print("Expected ranked hypotheses.")
            return 5

        top = hypotheses[0]
        top_text = " ".join([
            str(top.get("title", "")),
            " ".join(top.get("themes", [])),
            " ".join(top.get("symbols", [])),
        ]).lower()
        if not any(token in top_text for token in ["semiconductor", "ai infrastructure", "amd", "nvda"]):
            print(f"Top hypothesis is not theme-aware: {top}")
            return 6

        if float(top.get("theme_match_score") or 0.0) <= 0:
            print(f"Top hypothesis missing theme_match_score: {top}")
            return 7

        if int(packet.get("packet_quality_score") or 0) <= 0:
            print(f"Packet quality score missing/invalid: {packet.get('packet_quality_score')}")
            return 8

        paths = write_research_packet(fake_live, theme="AI infrastructure semiconductors", max_symbols=8)
        if not Path(paths["markdown_path"]).exists() or not Path(paths["json_path"]).exists():
            print(f"Research packet files missing: {paths}")
            return 9

    # Smoke-test against the real current database if present.
    real_packet = build_research_packet(live_root, theme="AI infrastructure semiconductors", max_symbols=12)
    if "packet_quality_score" not in real_packet or "warning_flags" not in real_packet:
        print("Real packet missing quality fields.")
        return 10

    print("v23.1.3 Theme-Aware Research Packet Ranking self-test: PASS")
    print(f"real_packet_quality_score: {real_packet.get('packet_quality_score')}")
    print(f"real_warning_flags: {real_packet.get('warning_flags')}")
    print(f"real_suggested_symbols: {','.join(real_packet.get('suggested_symbols', []))}")
    print("Research/simulation only. No broker calls or trade execution were made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
