from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import json_loads
from .storage import MarketMemoryStore, default_market_memory_paths
from .symbol_hygiene import is_valid_research_symbol, requested_theme_symbol_multiplier


KNOWN_THEMES = {
    "AI infrastructure",
    "Semiconductors",
    "Cloud platforms",
    "Interest rates",
    "Cybersecurity",
    "Energy",
    "Defense",
    "Healthcare",
    "Consumer discretionary",
}


def _decode(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    for key in list(out.keys()):
        if key.endswith("_json"):
            out[key[:-5]] = json_loads(out.pop(key), [])
    return out


def _safe_slug(text: str) -> str:
    out = []
    for ch in text:
        if ch.isalnum() or ch in {"-", "_"}:
            out.append(ch)
        elif ch.isspace():
            out.append("_")
    return "".join(out).strip("_")[:80] or "market_memory"


def _symbol_score_from_entities(entities: list[dict[str, Any]]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for row in entities:
        item = _decode(row)
        symbol = str(item.get("symbol") or "").upper().strip()
        if not symbol:
            continue
        score = float(item.get("source_count") or 1) * float(item.get("confidence") or 0.5)
        scores[symbol] = scores.get(symbol, 0.0) + score
    return scores


def _symbol_score_from_relationships(relationships: list[dict[str, Any]]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for row in relationships:
        item = _decode(row)
        metadata = item.get("metadata") or {}
        for key in ["symbol", "peer_symbol"]:
            symbol = str(metadata.get(key) or "").upper().strip()
            if symbol:
                scores[symbol] = scores.get(symbol, 0.0) + float(item.get("confidence") or 0.5)
    return scores


def _top_themes(entities: list[dict[str, Any]], relationships: list[dict[str, Any]], requested_theme: str = "") -> list[str]:
    theme_scores: dict[str, float] = {}
    requested_lower = requested_theme.lower().strip()

    for row in entities:
        item = _decode(row)
        if item.get("entity_type") == "theme":
            theme = str(item.get("canonical_name") or "").strip()
            if theme:
                score = float(item.get("source_count") or 1) * float(item.get("confidence") or 0.5)
                if requested_lower and requested_lower in theme.lower():
                    score += 5.0
                theme_scores[theme] = theme_scores.get(theme, 0.0) + score

    for row in relationships:
        item = _decode(row)
        for key in ["source_entity", "target_entity"]:
            value = str(item.get(key) or "").strip()
            if value in KNOWN_THEMES:
                score = float(item.get("confidence") or 0.5)
                if requested_lower and requested_lower in value.lower():
                    score += 5.0
                theme_scores[value] = theme_scores.get(value, 0.0) + score

    return [theme for theme, _score in sorted(theme_scores.items(), key=lambda kv: (-kv[1], kv[0]))[:8]]


def _preferred_strategy_families(strategy_rows: list[dict[str, Any]]) -> list[str]:
    scored: dict[str, float] = {}
    for row in strategy_rows:
        item = _decode(row)
        family = str(item.get("strategy_family") or "").strip()
        if not family or family == "unknown_strategy_family":
            continue
        status = str(item.get("status") or "")
        score = float(item.get("score") or 0.0)
        weight = 1.0 + score / 100.0
        if "rejected" in status or "rework" in status:
            weight *= 0.25
        elif "validated" in status or "partial" in status or "candidate" in status:
            weight *= 1.5
        scored[family] = scored.get(family, 0.0) + weight

    if not scored:
        return ["rsi_mean_reversion", "trend_following"]

    return [family for family, _score in sorted(scored.items(), key=lambda kv: (-kv[1], kv[0]))[:5]]


def build_research_packet(live_root: Path, theme: str = "", max_symbols: int = 12) -> dict[str, Any]:
    paths = default_market_memory_paths(live_root)
    store = MarketMemoryStore(paths["db_path"], paths["evidence_ledger_path"])

    entities = store.fetch_all("entities", limit=200)
    relationships = store.fetch_all("relationships", limit=250)
    hypotheses = store.fetch_all("hypotheses", limit=100)
    strategies = store.fetch_all("strategy_memory", limit=100)
    evidence = store.fetch_all("evidence_items", limit=25)

    scores = _symbol_score_from_entities(entities)
    for symbol, score in _symbol_score_from_relationships(relationships).items():
        scores[symbol] = scores.get(symbol, 0.0) + score

    max_symbols = max(1, min(int(max_symbols or 12), 30))
    adjusted_scores = {
        symbol: score * requested_theme_symbol_multiplier(symbol, theme)
        for symbol, score in scores.items()
        if is_valid_research_symbol(symbol)
    }

    ranked_symbols = [
        {"symbol": symbol, "score": round(score, 4)}
        for symbol, score in sorted(adjusted_scores.items(), key=lambda kv: (-kv[1], kv[0]))[:max_symbols]
    ]

    packet = {
        "schema_version": "market_memory_research_packet_v23_1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "research_simulation_only",
        "requested_theme": theme,
        "research_theme_candidates": _top_themes(entities, relationships, theme),
        "suggested_symbols": [item["symbol"] for item in ranked_symbols],
        "ranked_symbols": ranked_symbols,
        "preferred_strategy_families": _preferred_strategy_families(strategies),
        "validation_required": [
            "multi_symbol_backtest",
            "walk_forward_validation",
            "overfit_warning_review",
            "trade_count_check",
            "fees_slippage_stress_later",
        ],
        "hypotheses": [_decode(row) for row in hypotheses[:12]],
        "top_relationships": [_decode(row) for row in relationships[:30]],
        "recent_evidence": [_decode(row) for row in evidence[:15]],
        "safety_note": "Research packet only. Not a trade recommendation. Human review required.",
    }
    return packet


def render_research_packet_markdown(packet: dict[str, Any]) -> str:
    lines = [
        "# Market Memory Research Packet",
        "",
        "**Research/simulation only. This is not a trade recommendation. Human review required.**",
        "",
        f"- Generated at: `{packet.get('generated_at', '')}`",
        f"- Requested theme: `{packet.get('requested_theme') or 'none'}`",
        f"- Theme candidates: `{', '.join(packet.get('research_theme_candidates', [])) or 'none'}`",
        f"- Suggested symbols: `{', '.join(packet.get('suggested_symbols', [])) or 'none'}`",
        f"- Preferred strategy families: `{', '.join(packet.get('preferred_strategy_families', [])) or 'none'}`",
        "",
        "## Ranked symbols",
        "",
        "| Rank | Symbol | Score |",
        "|---:|---|---:|",
    ]

    for idx, row in enumerate(packet.get("ranked_symbols", []), start=1):
        lines.append(f"| {idx} | `{row.get('symbol')}` | {float(row.get('score', 0.0)):.2f} |")

    lines.extend(["", "## Hypotheses to test", ""])
    hypotheses = packet.get("hypotheses", [])
    if hypotheses:
        lines.extend(["| Status | Confidence | Title | Symbols | Themes |", "|---|---:|---|---|---|"])
        for row in hypotheses[:12]:
            lines.append(
                f"| {row.get('status', '')} | {float(row.get('confidence', 0.0)):.2f} | "
                f"{row.get('title', '')} | {', '.join(row.get('symbols', [])[:8])} | {', '.join(row.get('themes', [])[:5])} |"
            )
    else:
        lines.append("No hypotheses stored yet.")

    lines.extend(["", "## Strong relationships", ""])
    relationships = packet.get("top_relationships", [])
    if relationships:
        lines.extend(["| Source | Relationship | Target | Confidence | Evidence |", "|---|---|---|---:|---:|"])
        for row in relationships[:20]:
            lines.append(
                f"| {row.get('source_entity', '')} | {row.get('relationship_type', '')} | "
                f"{row.get('target_entity', '')} | {float(row.get('confidence', 0.0)):.2f} | {row.get('evidence_count', 0)} |"
            )
    else:
        lines.append("No relationships stored yet.")

    lines.extend(
        [
            "",
            "## Recommended Auto Lab workflow",
            "",
            "1. Review/edit suggested symbols.",
            "2. Run Universe Auto Lab across the full basket.",
            "3. Run Walk-Forward Validation on top candidates.",
            "4. Reject strategies with weak out-of-sample behavior.",
            "5. Feed results back into Market Memory.",
            "",
            "Do not use this packet for live orders.",
            "",
        ]
    )
    return "\n".join(lines)


def write_research_packet(live_root: Path, theme: str = "", max_symbols: int = 12) -> dict[str, str]:
    packet = build_research_packet(live_root, theme=theme, max_symbols=max_symbols)
    base = live_root / "data" / "market_memory" / "research_packets"
    base.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    slug = _safe_slug(theme or "market_memory")
    json_path = base / f"{stamp}_{slug}_research_packet.json"
    md_path = base / f"{stamp}_{slug}_research_packet.md"

    json_path.write_text(json.dumps(packet, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_research_packet_markdown(packet), encoding="utf-8")

    return {
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "suggested_symbols": ",".join(packet.get("suggested_symbols", [])),
        "preferred_strategy_families": ",".join(packet.get("preferred_strategy_families", [])),
    }
