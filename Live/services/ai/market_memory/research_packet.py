from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import json_loads
from .storage import MarketMemoryStore, default_market_memory_paths
from .symbol_hygiene import is_valid_research_symbol, requested_theme_symbol_multiplier
from .theme_ranking import (
    build_theme_match_summary,
    packet_quality_score_and_warnings,
    rank_rows_by_theme,
)


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
        if not symbol or not is_valid_research_symbol(symbol):
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
            if symbol and is_valid_research_symbol(symbol):
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
                if requested_lower and theme.lower() in requested_lower:
                    score += 8.0
                elif requested_lower and any(word in requested_lower for word in theme.lower().split()):
                    score += 3.0
                theme_scores[theme] = theme_scores.get(theme, 0.0) + score

    for row in relationships:
        item = _decode(row)
        for key in ["source_entity", "target_entity"]:
            value = str(item.get(key) or "").strip()
            if value in KNOWN_THEMES:
                score = float(item.get("confidence") or 0.5)
                if requested_lower and value.lower() in requested_lower:
                    score += 8.0
                elif requested_lower and any(word in requested_lower for word in value.lower().split()):
                    score += 3.0
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

    entities = store.fetch_all("entities", limit=250)
    relationships_raw = store.fetch_all("relationships", limit=350)
    hypotheses_raw = store.fetch_all("hypotheses", limit=200)
    strategies = store.fetch_all("strategy_memory", limit=120)
    evidence_raw = store.fetch_all("evidence_items", limit=80)

    scores = _symbol_score_from_entities(entities)
    for symbol, score in _symbol_score_from_relationships(relationships_raw).items():
        scores[symbol] = scores.get(symbol, 0.0) + score

    adjusted_scores = {
        symbol: score * requested_theme_symbol_multiplier(symbol, theme)
        for symbol, score in scores.items()
        if is_valid_research_symbol(symbol)
    }

    max_symbols = max(1, min(int(max_symbols or 12), 30))
    ranked_symbols = [
        {"symbol": symbol, "score": round(score, 4)}
        for symbol, score in sorted(adjusted_scores.items(), key=lambda kv: (-kv[1], kv[0]))[:max_symbols]
    ]

    hypotheses = [_decode(row) for row in hypotheses_raw]
    relationships = [_decode(row) for row in relationships_raw]
    evidence = [_decode(row) for row in evidence_raw]

    ranked_hypotheses = rank_rows_by_theme(
        hypotheses,
        theme,
        fallback_score_keys=["confidence"],
    )[:12]
    ranked_relationships = rank_rows_by_theme(
        relationships,
        theme,
        fallback_score_keys=["confidence", "evidence_count", "impact_score"],
    )[:30]
    ranked_evidence = rank_rows_by_theme(
        evidence,
        theme,
        fallback_score_keys=["source_count"],
    )[:15]

    packet = {
        "schema_version": "market_memory_research_packet_v23_1_3",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "research_simulation_only",
        "requested_theme": theme,
        "research_theme_candidates": _top_themes(entities, relationships_raw, theme),
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
        "hypotheses": ranked_hypotheses,
        "top_relationships": ranked_relationships,
        "recent_evidence": ranked_evidence,
        "theme_match_summary": {},
        "packet_quality_score": 0,
        "warning_flags": [],
        "safety_note": "Research packet only. Not a trade recommendation. Human review required.",
    }

    packet["theme_match_summary"] = build_theme_match_summary(
        requested_theme=theme,
        ranked_symbols=ranked_symbols,
        hypotheses=ranked_hypotheses,
        relationships=ranked_relationships,
    )
    quality, warnings = packet_quality_score_and_warnings(packet)
    packet["packet_quality_score"] = quality
    packet["warning_flags"] = warnings

    return packet


def render_research_packet_markdown(packet: dict[str, Any]) -> str:
    warnings = packet.get("warning_flags", [])
    theme_summary = packet.get("theme_match_summary", {})

    lines = [
        "# Market Memory Research Packet",
        "",
        "**Research/simulation only. This is not a trade recommendation. Human review required.**",
        "",
        f"- Generated at: `{packet.get('generated_at', '')}`",
        f"- Requested theme: `{packet.get('requested_theme') or 'none'}`",
        f"- Packet quality score: `{packet.get('packet_quality_score', 0)}/100`",
        f"- Warning flags: `{', '.join(warnings) if warnings else 'none'}`",
        f"- Theme candidates: `{', '.join(packet.get('research_theme_candidates', [])) or 'none'}`",
        f"- Suggested symbols: `{', '.join(packet.get('suggested_symbols', [])) or 'none'}`",
        f"- Preferred strategy families: `{', '.join(packet.get('preferred_strategy_families', [])) or 'none'}`",
        "",
        "## Theme match summary",
        "",
        f"- Matched terms: `{', '.join(theme_summary.get('matched_terms', [])) or 'none'}`",
        f"- Theme-relevant symbols: `{', '.join(theme_summary.get('theme_relevant_symbols', [])) or 'none'}`",
        f"- Off-theme symbols: `{', '.join(theme_summary.get('off_theme_symbols', [])) or 'none'}`",
        f"- Top hypothesis theme score: `{theme_summary.get('top_hypothesis_theme_match_score', 0)}`",
        f"- Top relationship theme score: `{theme_summary.get('top_relationship_theme_match_score', 0)}`",
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
        lines.extend(["| Status | Theme Score | Confidence | Title | Symbols | Themes |", "|---|---:|---:|---|---|---|"])
        for row in hypotheses[:12]:
            lines.append(
                f"| {row.get('status', '')} | {float(row.get('theme_match_score', 0.0)):.2f} | "
                f"{float(row.get('confidence', 0.0)):.2f} | {row.get('title', '')} | "
                f"{', '.join(row.get('symbols', [])[:8])} | {', '.join(row.get('themes', [])[:5])} |"
            )
    else:
        lines.append("No hypotheses stored yet.")

    lines.extend(["", "## Strong relationships", ""])
    relationships = packet.get("top_relationships", [])
    if relationships:
        lines.extend(["| Source | Relationship | Target | Theme Score | Confidence | Evidence |", "|---|---|---|---:|---:|---:|"])
        for row in relationships[:20]:
            lines.append(
                f"| {row.get('source_entity', '')} | {row.get('relationship_type', '')} | "
                f"{row.get('target_entity', '')} | {float(row.get('theme_match_score', 0.0)):.2f} | "
                f"{float(row.get('confidence', 0.0)):.2f} | {row.get('evidence_count', 0)} |"
            )
    else:
        lines.append("No relationships stored yet.")

    lines.extend(
        [
            "",
            "## Recommended Auto Lab workflow",
            "",
            "1. Review packet quality and warning flags.",
            "2. Review/edit suggested symbols.",
            "3. Run Universe Auto Lab across the full basket.",
            "4. Run Walk-Forward Validation on top candidates.",
            "5. Reject strategies with weak out-of-sample behavior.",
            "6. Feed results back into Market Memory.",
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
        "packet_quality_score": str(packet.get("packet_quality_score", 0)),
        "warning_flags": ",".join(packet.get("warning_flags", [])),
    }
