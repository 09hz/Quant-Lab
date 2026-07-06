from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import json_loads, utc_now_iso
from .storage import MarketMemoryStore, default_market_memory_paths


def _decode_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    for key in list(out.keys()):
        if key.endswith("_json"):
            out[key[:-5]] = json_loads(out.pop(key), [])
    return out


def _table_rows(rows: list[dict[str, Any]], columns: list[str]) -> list[str]:
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for row in rows:
        decoded = _decode_row(row)
        vals = []
        for col in columns:
            value = decoded.get(col, "")
            if isinstance(value, list):
                value = ", ".join(str(x) for x in value[:8])
            elif isinstance(value, dict):
                value = json.dumps(value, ensure_ascii=False)[:160]
            vals.append(str(value).replace("\n", " ")[:220])
        lines.append("| " + " | ".join(vals) + " |")
    return lines


def build_snapshot(store: MarketMemoryStore) -> dict[str, Any]:
    return {
        "schema_version": "market_memory_snapshot_v23_0",
        "generated_at": utc_now_iso(),
        "counts": store.summary_counts(),
        "recent_evidence": [_decode_row(row) for row in store.fetch_all("evidence_items", limit=25)],
        "top_entities": [_decode_row(row) for row in store.fetch_all("entities", limit=50)],
        "top_relationships": [_decode_row(row) for row in store.fetch_all("relationships", limit=50)],
        "open_hypotheses": [_decode_row(row) for row in store.fetch_all("hypotheses", limit=25)],
        "recent_research_runs": [_decode_row(row) for row in store.fetch_all("research_runs", limit=25)],
        "strategy_memory": [_decode_row(row) for row in store.fetch_all("strategy_memory", limit=25)],
        "safety_note": "Research/simulation only. This memory layer does not place orders or connect to brokers.",
    }


def render_market_memory_report(snapshot: dict[str, Any]) -> str:
    counts = snapshot.get("counts", {})
    lines = [
        "# Market Memory Report",
        "",
        "**Research/simulation only. This memory layer does not place orders or connect to brokers.**",
        "",
        f"- Generated at: `{snapshot.get('generated_at', '')}`",
        f"- Evidence items: `{counts.get('evidence_items', 0)}`",
        f"- Entities: `{counts.get('entities', 0)}`",
        f"- Relationships: `{counts.get('relationships', 0)}`",
        f"- Hypotheses: `{counts.get('hypotheses', 0)}`",
        f"- Research runs: `{counts.get('research_runs', 0)}`",
        f"- Strategy memory items: `{counts.get('strategy_memory', 0)}`",
        "",
        "## Top entities",
        "",
    ]
    lines.extend(_table_rows(snapshot.get("top_entities", [])[:20], ["canonical_name", "entity_type", "symbol", "source_count", "confidence", "last_seen_at"]))
    lines.extend(["", "## Top relationships", ""])
    lines.extend(_table_rows(snapshot.get("top_relationships", [])[:25], ["source_entity", "relationship_type", "target_entity", "confidence", "evidence_count", "last_seen_at"]))
    lines.extend(["", "## Recent evidence", ""])
    lines.extend(_table_rows(snapshot.get("recent_evidence", [])[:20], ["title", "source_type", "symbols", "themes", "ingested_at"]))

    lines.extend(["", "## Open / Active Hypotheses", ""])
    hypotheses = snapshot.get("open_hypotheses", [])[:15]
    if hypotheses:
        lines.extend(_table_rows(hypotheses, ["title", "status", "confidence", "symbols", "themes", "updated_at"]))
    else:
        lines.append("No hypotheses stored yet.")

    lines.extend(["", "## Strategy Memory", ""])
    strategies = snapshot.get("strategy_memory", [])[:15]
    if strategies:
        lines.extend(_table_rows(strategies, ["strategy_name", "strategy_family", "status", "score", "symbols", "updated_at"]))
    else:
        lines.append("No strategy memory stored yet.")
    lines.extend(
        [
            "",
            "## How to use this",
            "",
            "1. Use relationships to identify connected symbols and themes.",
            "2. Use evidence to trace why the memory exists.",
            "3. Use Auto Lab and walk-forward results to validate or reject hypotheses.",
            "4. Feed stronger relationship packets into future AI research cycles.",
            "",
        ]
    )
    return "\n".join(lines)


def render_entity_report(snapshot: dict[str, Any]) -> str:
    lines = [
        "# Market Memory Entity Report",
        "",
        "**Entities are symbols, companies, sectors, themes, and market concepts observed by the researcher.**",
        "",
    ]
    lines.extend(_table_rows(snapshot.get("top_entities", []), ["canonical_name", "entity_type", "symbol", "aliases", "source_count", "confidence", "first_seen_at", "last_seen_at"]))
    return "\n".join(lines) + "\n"


def render_relationship_report(snapshot: dict[str, Any]) -> str:
    lines = [
        "# Market Memory Relationship Report",
        "",
        "**Relationships show the AI researcher's current connection web. They are research signals, not trading instructions.**",
        "",
    ]
    lines.extend(_table_rows(snapshot.get("top_relationships", []), ["source_entity", "relationship_type", "target_entity", "confidence", "impact_score", "recency_score", "evidence_count", "evidence_ids"]))
    return "\n".join(lines) + "\n"


def render_hypothesis_report(snapshot: dict[str, Any]) -> str:
    lines = [
        "# Market Memory Hypothesis Report",
        "",
        "**Hypotheses are research ideas that still require backtesting and walk-forward validation.**",
        "",
    ]
    rows = snapshot.get("open_hypotheses", [])
    if rows:
        lines.extend(_table_rows(rows, ["title", "status", "confidence", "symbols", "themes", "updated_at"]))
    else:
        lines.append("No hypotheses stored yet.")
    return "\n".join(lines) + "\n"


def write_memory_reports(live_root: Path) -> dict[str, str]:
    paths = default_market_memory_paths(live_root)
    store = MarketMemoryStore(paths["db_path"], paths["evidence_ledger_path"])
    reports_dir = paths["reports_dir"]
    reports_dir.mkdir(parents=True, exist_ok=True)

    snapshot = build_snapshot(store)

    snapshot_path = reports_dir / "memory_snapshot.json"
    market_report_path = reports_dir / "market_memory_report.md"
    entity_report_path = reports_dir / "entity_report.md"
    relationship_report_path = reports_dir / "relationship_report.md"
    hypothesis_report_path = reports_dir / "hypothesis_report.md"

    snapshot_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    market_report_path.write_text(render_market_memory_report(snapshot), encoding="utf-8")
    entity_report_path.write_text(render_entity_report(snapshot), encoding="utf-8")
    relationship_report_path.write_text(render_relationship_report(snapshot), encoding="utf-8")
    hypothesis_report_path.write_text(render_hypothesis_report(snapshot), encoding="utf-8")

    return {
        "snapshot_path": str(snapshot_path),
        "market_report_path": str(market_report_path),
        "entity_report_path": str(entity_report_path),
        "relationship_report_path": str(relationship_report_path),
        "hypothesis_report_path": str(hypothesis_report_path),
        "db_path": str(paths["db_path"]),
        "evidence_ledger_path": str(paths["evidence_ledger_path"]),
    }
