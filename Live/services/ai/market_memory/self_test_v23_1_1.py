from __future__ import annotations

from pathlib import Path
import ast
import sys


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def main() -> int:
    repo_root = _repo_root()
    live_root = repo_root / "Live"
    package_dir = live_root / "services" / "ai" / "market_memory"

    required = [
        package_dir / "symbol_hygiene.py",
        package_dir / "relationship_engine.py",
        package_dir / "hypothesis_engine.py",
        package_dir / "research_packet.py",
        package_dir / "ingest.py",
    ]

    for path in required:
        if not path.exists():
            print(f"Missing {path}")
            return 2
        ast.parse(path.read_text(encoding="utf-8", errors="replace"))

    if str(live_root) not in sys.path:
        sys.path.insert(0, str(live_root))

    from services.ai.market_memory.symbol_hygiene import clean_symbol_list
    from services.ai.market_memory.relationship_engine import extract_memory_signals
    from services.ai.market_memory.research_packet import build_research_packet

    noisy = ["AI", "PASS", "ENV", "WARN", "IB", "SEND", "LIVE", "AMD", "NVDA", "TSM", "ASML", "SMH"]
    cleaned = clean_symbol_list(noisy)
    forbidden = {"AI", "PASS", "ENV", "WARN", "IB", "SEND", "LIVE"}

    if forbidden.intersection(cleaned):
        print(f"Noise symbols were not filtered: {cleaned}")
        return 3

    for required_symbol in ["AMD", "NVDA", "TSM", "ASML", "SMH"]:
        if required_symbol not in cleaned:
            print(f"Expected symbol missing after cleaning: {required_symbol}, cleaned={cleaned}")
            return 4

    signals = extract_memory_signals(
        "PASS ENV WARN SEND LIVE AI AMD NVDA TSM ASML semiconductors AI infrastructure",
        metadata={"symbols": ["AI", "PASS", "AMD", "NVDA", "SMH"], "themes": ["AI infrastructure", "Semiconductors"]},
    )
    if forbidden.intersection(signals.get("symbols", [])):
        print(f"Relationship engine extracted noise symbols: {signals}")
        return 5

    packet = build_research_packet(live_root, theme="AI infrastructure semiconductors", max_symbols=12)
    suggested = packet.get("suggested_symbols", [])
    bad = forbidden.intersection(suggested)
    if bad:
        print(f"Research packet still includes noise symbols: {bad}, suggested={suggested}")
        return 6

    if "AMD" not in suggested or "NVDA" not in suggested:
        print(f"Expected AMD/NVDA in suggested symbols, got {suggested}")
        return 7

    print("v23.1.1 Market Memory Symbol Hygiene self-test: PASS")
    print(f"cleaned_symbols: {cleaned}")
    print(f"current_packet_suggested_symbols: {','.join(suggested)}")
    print("Research/simulation only. No broker calls or trade execution were made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
