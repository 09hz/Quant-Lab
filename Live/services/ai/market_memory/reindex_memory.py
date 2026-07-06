from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .hypothesis_engine import hypotheses_from_evidence, strategy_memory_from_text
from .models import json_dumps, json_loads
from .reports import write_memory_reports
from .research_packet import write_research_packet
from .storage import MarketMemoryStore, default_market_memory_paths
from .symbol_hygiene import NOISE_SYMBOLS, clean_symbol_list, is_valid_research_symbol


def _find_repo_root(start: Path) -> Path:
    start = start.resolve()
    for candidate in [start, *start.parents]:
        if (candidate / "Live" / "app.py").exists() and (candidate / "Live" / "services").is_dir():
            return candidate
        if (candidate / "app.py").exists() and candidate.name.lower() == "live":
            return candidate.parent
    raise SystemExit("Could not locate repo root containing Live/app.py")


def _clean_entities(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()

    for entity in entities or []:
        if not isinstance(entity, dict):
            continue

        entity_type = str(entity.get("entity_type") or "").strip()
        symbol = str(entity.get("symbol") or "").strip().upper()
        canonical = str(entity.get("canonical_name") or "").strip()

        if entity_type == "symbol":
            if not is_valid_research_symbol(symbol):
                continue
            key = f"symbol:{symbol}"
        else:
            if canonical.upper() in NOISE_SYMBOLS:
                continue
            key = f"{entity_type}:{canonical.lower()}"

        if key in seen:
            continue
        seen.add(key)
        cleaned.append(entity)

    return cleaned


def _metadata_has_bad_symbol(metadata: dict[str, Any]) -> bool:
    for key in ["symbol", "peer_symbol"]:
        value = str(metadata.get(key) or "").strip().upper()
        if value and not is_valid_research_symbol(value):
            return True
    return False


def reindex_market_memory(live_root: Path, theme: str = "AI infrastructure semiconductors", max_symbols: int = 12) -> dict[str, Any]:
    """Clean old noisy rows and rebuild derived market-memory tables.

    This is research/simulation-only data maintenance.
    """
    paths = default_market_memory_paths(live_root)
    store = MarketMemoryStore(paths["db_path"], paths["evidence_ledger_path"])

    result: dict[str, Any] = {
        "evidence_rows_cleaned": 0,
        "entities_deleted": 0,
        "relationships_deleted": 0,
        "hypotheses_rebuilt": 0,
        "strategy_memory_rebuilt": 0,
        "reports": {},
        "research_packet": {},
    }

    with store.session() as conn:
        evidence_rows = conn.execute("SELECT * FROM evidence_items").fetchall()

        for row in evidence_rows:
            symbols = clean_symbol_list(json_loads(row["symbols_json"], []))
            entities = _clean_entities(json_loads(row["entities_json"], []))

            if symbols != json_loads(row["symbols_json"], []) or entities != json_loads(row["entities_json"], []):
                conn.execute(
                    """
                    UPDATE evidence_items
                    SET symbols_json = ?, entities_json = ?
                    WHERE id = ?
                    """,
                    (json_dumps(symbols), json_dumps(entities), row["id"]),
                )
                result["evidence_rows_cleaned"] += 1

        entity_rows = conn.execute("SELECT canonical_name, entity_type, symbol FROM entities").fetchall()
        for row in entity_rows:
            canonical = str(row["canonical_name"] or "")
            entity_type = str(row["entity_type"] or "")
            symbol = str(row["symbol"] or "").upper().strip()

            delete = False
            if entity_type == "symbol" and not is_valid_research_symbol(symbol):
                delete = True
            if canonical.upper() in NOISE_SYMBOLS:
                delete = True

            if delete:
                conn.execute("DELETE FROM entities WHERE canonical_name = ?", (canonical,))
                result["entities_deleted"] += 1

        rel_rows = conn.execute("SELECT id, source_entity, target_entity, metadata_json FROM relationships").fetchall()
        for row in rel_rows:
            source = str(row["source_entity"] or "").strip()
            target = str(row["target_entity"] or "").strip()
            metadata = json_loads(row["metadata_json"], {})

            delete = False
            if source.upper() in NOISE_SYMBOLS or target.upper() in NOISE_SYMBOLS:
                delete = True
            if isinstance(metadata, dict) and _metadata_has_bad_symbol(metadata):
                delete = True

            if delete:
                conn.execute("DELETE FROM relationships WHERE id = ?", (row["id"],))
                result["relationships_deleted"] += 1

        # Rebuild derived tables from cleaned evidence.
        conn.execute("DELETE FROM hypotheses")
        conn.execute("DELETE FROM strategy_memory")

        cleaned_evidence_rows = conn.execute("SELECT * FROM evidence_items").fetchall()
        for row in cleaned_evidence_rows:
            evidence_id = row["id"]
            source_type = row["source_type"]
            title = row["title"]
            text = " ".join([row["title"] or "", row["summary"] or ""])
            symbols = clean_symbol_list(json_loads(row["symbols_json"], []))
            themes = json_loads(row["themes_json"], [])
            metadata = json_loads(row["metadata_json"], {})

            hypotheses = hypotheses_from_evidence(
                evidence_id=evidence_id,
                source_type=source_type,
                title=title,
                text=text,
                symbols=symbols,
                themes=themes,
                metadata=metadata,
            )
            for hypothesis in hypotheses:
                # Save directly through conn to avoid nested store.session calls.
                conn.execute(
                    """
                    INSERT OR REPLACE INTO hypotheses (
                        id, title, thesis, status, confidence, symbols_json, themes_json,
                        evidence_ids_json, created_at, updated_at, metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        hypothesis.id,
                        hypothesis.title,
                        hypothesis.thesis,
                        hypothesis.status,
                        float(hypothesis.confidence),
                        json_dumps(hypothesis.symbols),
                        json_dumps(hypothesis.themes),
                        json_dumps(hypothesis.evidence_ids),
                        hypothesis.created_at,
                        hypothesis.updated_at,
                        json_dumps(hypothesis.metadata),
                    ),
                )
                result["hypotheses_rebuilt"] += 1

            strategy_items = strategy_memory_from_text(
                evidence_id=evidence_id,
                source_type=source_type,
                title=title,
                text=text,
                symbols=symbols,
                themes=themes,
                metadata=metadata,
            )
            for item in strategy_items:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO strategy_memory (
                        id, strategy_name, strategy_family, status, score, symbols_json,
                        result_refs_json, created_at, updated_at, metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.id,
                        item.strategy_name,
                        item.strategy_family,
                        item.status,
                        float(item.score),
                        json_dumps(item.symbols),
                        json_dumps(item.result_refs),
                        item.created_at,
                        item.updated_at,
                        json_dumps(item.metadata),
                    ),
                )
                result["strategy_memory_rebuilt"] += 1

    reports = write_memory_reports(live_root)
    packet = write_research_packet(live_root, theme=theme, max_symbols=max_symbols)

    result["reports"] = reports
    result["research_packet"] = packet
    result["counts"] = store.summary_counts()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean and reindex Market Memory after symbol hygiene upgrade.")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--theme", default="AI infrastructure semiconductors")
    parser.add_argument("--max-symbols", type=int, default=12)
    parser.add_argument("--print-json", action="store_true")
    args = parser.parse_args()

    repo_root = _find_repo_root(args.repo_root or Path.cwd())
    live_root = repo_root / "Live"

    if str(live_root) not in sys.path:
        sys.path.insert(0, str(live_root))

    result = reindex_market_memory(live_root, theme=args.theme, max_symbols=args.max_symbols)

    print("Market memory reindex and cleanup complete.")
    print(f"- repo_root: {repo_root}")
    print(f"- evidence_rows_cleaned: {result.get('evidence_rows_cleaned')}")
    print(f"- entities_deleted: {result.get('entities_deleted')}")
    print(f"- relationships_deleted: {result.get('relationships_deleted')}")
    print(f"- hypotheses_rebuilt: {result.get('hypotheses_rebuilt')}")
    print(f"- strategy_memory_rebuilt: {result.get('strategy_memory_rebuilt')}")
    print(f"- counts: {result.get('counts')}")
    print(f"- market_report_path: {result.get('reports', {}).get('market_report_path')}")
    print(f"- research_packet_markdown: {result.get('research_packet', {}).get('markdown_path')}")
    print(f"- research_packet_symbols: {result.get('research_packet', {}).get('suggested_symbols')}")
    print()
    print("Research/simulation only. No broker calls or trade execution were made.")

    if args.print_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
