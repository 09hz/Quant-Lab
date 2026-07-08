from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def find_live_root(start: Path | None = None) -> Path:
    start = (start or Path(__file__)).resolve()
    for candidate in [start, *start.parents]:
        if candidate.name.lower() == "live" and (candidate / "app.py").exists():
            return candidate
        if (candidate / "Live" / "app.py").exists():
            return candidate / "Live"
    raise RuntimeError("Could not locate Live root containing app.py")


def _packet_dir(live_root: Path) -> Path:
    return live_root / "data" / "market_memory" / "research_packets"


def find_latest_packet_json(live_root: Path | None = None) -> Path | None:
    live_root = find_live_root(live_root)
    packet_dir = _packet_dir(live_root)
    if not packet_dir.exists():
        return None
    candidates = sorted(packet_dir.glob("*_research_packet.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def load_packet_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


def build_memory_packet(live_root: Path | None = None, theme: str = "AI infrastructure semiconductors", max_symbols: int = 12) -> dict[str, str]:
    live_root = find_live_root(live_root)
    from services.ai.market_memory.research_packet import write_research_packet
    return write_research_packet(live_root, theme=theme, max_symbols=max_symbols)


def load_or_build_market_memory_packet(
    live_root: Path | None = None,
    theme: str = "AI infrastructure semiconductors",
    max_symbols: int = 12,
    rebuild: bool = True,
) -> dict[str, Any]:
    """Load or rebuild the latest Market Memory research packet.

    Research/simulation only. This function never calls brokers or executes trades.
    """
    live_root = find_live_root(live_root)
    packet_paths: dict[str, str] = {}
    if rebuild:
        packet_paths = build_memory_packet(live_root, theme=theme, max_symbols=max_symbols)

    packet_path = Path(packet_paths.get("json_path") or "") if packet_paths else None
    if not packet_path or not packet_path.exists():
        packet_path = find_latest_packet_json(live_root)

    if not packet_path or not packet_path.exists():
        raise FileNotFoundError("No Market Memory research packet found. Build one first.")

    packet = load_packet_json(packet_path)
    markdown_path = packet_paths.get("markdown_path")
    if not markdown_path:
        possible_md = packet_path.with_suffix(".md")
        markdown_path = str(possible_md) if possible_md.exists() else ""
    return {"packet": packet, "json_path": str(packet_path), "markdown_path": markdown_path}


def packet_symbols(packet: dict[str, Any]) -> list[str]:
    symbols = packet.get("suggested_symbols") or []
    return [str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()]


def packet_symbols_csv(packet: dict[str, Any]) -> str:
    return ",".join(packet_symbols(packet))


def format_packet_preview(result: dict[str, Any]) -> str:
    packet = result.get("packet") or {}
    symbols = packet_symbols(packet)
    hypotheses = packet.get("hypotheses") or []
    relationships = packet.get("top_relationships") or []
    quality = packet.get("packet_quality_score", "unknown")
    warnings = packet.get("warning_flags") or []
    families = packet.get("preferred_strategy_families") or []
    theme_summary = packet.get("theme_match_summary") or {}

    quality_line = f"- Packet quality score: `{quality}/100`" if isinstance(quality, int) else f"- Packet quality score: `{quality}`"

    lines = [
        "### Loaded Market Memory Research Packet",
        "",
        "**Research/simulation only. This is not a trade recommendation.**",
        "",
        quality_line,
        f"- Warning flags: `{', '.join(warnings) if warnings else 'none'}`",
        f"- Requested theme: `{packet.get('requested_theme') or 'none'}`",
        f"- Suggested symbols: `{', '.join(symbols) if symbols else 'none'}`",
        f"- Preferred strategy families: `{', '.join(families) if families else 'none'}`",
        f"- JSON path: `{result.get('json_path', '')}`",
        f"- Markdown path: `{result.get('markdown_path', '')}`",
        "",
        "#### Theme match summary",
        "",
        f"- Matched terms: `{', '.join(theme_summary.get('matched_terms', [])) or 'none'}`",
        f"- Theme-relevant symbols: `{', '.join(theme_summary.get('theme_relevant_symbols', [])) or 'none'}`",
        f"- Off-theme symbols: `{', '.join(theme_summary.get('off_theme_symbols', [])) or 'none'}`",
        "",
        "#### Top hypotheses",
        "",
    ]

    if hypotheses:
        lines.extend(["| Status | Theme Score | Confidence | Title | Symbols |", "|---|---:|---:|---|---|"])
        for row in hypotheses[:8]:
            lines.append(
                f"| {row.get('status', '')} | {float(row.get('theme_match_score') or 0.0):.2f} | "
                f"{float(row.get('confidence') or 0.0):.2f} | {row.get('title', '')} | "
                f"{', '.join(row.get('symbols', [])[:8])} |"
            )
    else:
        lines.append("No hypotheses found in this packet.")

    lines.extend(["", "#### Strong relationships", ""])
    if relationships:
        lines.extend(["| Source | Relationship | Target | Theme Score |", "|---|---|---|---:|"])
        for row in relationships[:8]:
            lines.append(
                f"| {row.get('source_entity', '')} | {row.get('relationship_type', '')} | "
                f"{row.get('target_entity', '')} | {float(row.get('theme_match_score') or 0.0):.2f} |"
            )
    else:
        lines.append("No relationships found in this packet.")

    return "\n".join(lines)

# BEGIN v24.6 direct producer wiring
try:
    from services.quant_schema.producer_runtime import wire_current_module
    wire_current_module(__name__, globals())
except Exception as _v24_6_direct_wiring_exc:
    print(f"[v24.6 direct producer wiring] disabled for {__name__}: {type(_v24_6_direct_wiring_exc).__name__}: {_v24_6_direct_wiring_exc}")
# END v24.6 direct producer wiring
