from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .models import (
    EntityRecord,
    EvidenceItem,
    HypothesisRecord,
    RelationshipRecord,
    ResearchRunRecord,
    StrategyMemoryRecord,
    json_dumps,
    json_loads,
    utc_now_iso,
)


def default_market_memory_paths(live_root: Path) -> dict[str, Path]:
    base = live_root / "data" / "market_memory"
    return {
        "base_dir": base,
        "db_path": base / "market_memory.sqlite",
        "evidence_ledger_path": base / "evidence_ledger.jsonl",
        "reports_dir": base / "memory_reports",
    }


class MarketMemoryStore:
    """SQLite-backed market memory ledger.

    Research/simulation only. This class has no broker/order behavior.
    """

    def __init__(self, db_path: Path, evidence_ledger_path: Path | None = None):
        self.db_path = Path(db_path)
        self.evidence_ledger_path = Path(evidence_ledger_path) if evidence_ledger_path else self.db_path.with_name("evidence_ledger.jsonl")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.evidence_ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @contextmanager
    def session(self):
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_db(self) -> None:
        with self.session() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS evidence_items (
                    id TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    ingested_at TEXT NOT NULL,
                    symbols_json TEXT NOT NULL,
                    entities_json TEXT NOT NULL,
                    themes_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_evidence_source_type ON evidence_items(source_type);
                CREATE INDEX IF NOT EXISTS idx_evidence_observed_at ON evidence_items(observed_at);

                CREATE TABLE IF NOT EXISTS entities (
                    canonical_name TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    symbol TEXT NOT NULL DEFAULT '',
                    aliases_json TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    source_count INTEGER NOT NULL DEFAULT 1,
                    confidence REAL NOT NULL DEFAULT 0.5,
                    metadata_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
                CREATE INDEX IF NOT EXISTS idx_entities_symbol ON entities(symbol);

                CREATE TABLE IF NOT EXISTS relationships (
                    id TEXT PRIMARY KEY,
                    source_entity TEXT NOT NULL,
                    target_entity TEXT NOT NULL,
                    relationship_type TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 0.5,
                    impact_score REAL NOT NULL DEFAULT 0.5,
                    recency_score REAL NOT NULL DEFAULT 1.0,
                    evidence_count INTEGER NOT NULL DEFAULT 1,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    evidence_ids_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_relationships_source ON relationships(source_entity);
                CREATE INDEX IF NOT EXISTS idx_relationships_target ON relationships(target_entity);
                CREATE INDEX IF NOT EXISTS idx_relationships_type ON relationships(relationship_type);

                CREATE TABLE IF NOT EXISTS hypotheses (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    thesis TEXT NOT NULL,
                    status TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 0.5,
                    symbols_json TEXT NOT NULL,
                    themes_json TEXT NOT NULL,
                    evidence_ids_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_hypotheses_status ON hypotheses(status);

                CREATE TABLE IF NOT EXISTS research_runs (
                    id TEXT PRIMARY KEY,
                    run_type TEXT NOT NULL,
                    run_path TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT NOT NULL,
                    metrics_json TEXT NOT NULL,
                    symbols_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_research_runs_type ON research_runs(run_type);
                CREATE INDEX IF NOT EXISTS idx_research_runs_status ON research_runs(status);

                CREATE TABLE IF NOT EXISTS strategy_memory (
                    id TEXT PRIMARY KEY,
                    strategy_name TEXT NOT NULL,
                    strategy_family TEXT NOT NULL,
                    status TEXT NOT NULL,
                    score REAL NOT NULL DEFAULT 0.0,
                    symbols_json TEXT NOT NULL,
                    result_refs_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_strategy_memory_family ON strategy_memory(strategy_family);
                CREATE INDEX IF NOT EXISTS idx_strategy_memory_status ON strategy_memory(status);
                """
            )
            now = utc_now_iso()
            conn.execute(
                "INSERT OR REPLACE INTO meta(key, value, updated_at) VALUES (?, ?, ?)",
                ("schema_version", "market_memory_v23_0", now),
            )

    def append_evidence_ledger(self, item: EvidenceItem) -> None:
        with self.evidence_ledger_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(item.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")

    def save_evidence(self, item: EvidenceItem) -> bool:
        """Save evidence item.

        Returns True when inserted, False when it was already present.
        """
        with self.session() as conn:
            existing = conn.execute("SELECT id FROM evidence_items WHERE id = ?", (item.id,)).fetchone()
            if existing:
                return False

            conn.execute(
                """
                INSERT INTO evidence_items (
                    id, source_type, source_path, title, summary, content_hash,
                    observed_at, ingested_at, symbols_json, entities_json, themes_json, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    item.source_type,
                    item.source_path,
                    item.title,
                    item.summary,
                    item.content_hash,
                    item.observed_at,
                    item.ingested_at,
                    json_dumps(item.symbols),
                    json_dumps(item.entities),
                    json_dumps(item.themes),
                    json_dumps(item.metadata),
                ),
            )
        self.append_evidence_ledger(item)
        return True

    def upsert_entity(self, entity: EntityRecord) -> None:
        now = entity.last_seen_at or utc_now_iso()
        first_seen = entity.first_seen_at or now
        aliases = list(dict.fromkeys(entity.aliases + [entity.canonical_name]))
        with self.session() as conn:
            old = conn.execute(
                "SELECT * FROM entities WHERE canonical_name = ?",
                (entity.canonical_name,),
            ).fetchone()
            if old:
                old_aliases = json_loads(old["aliases_json"], [])
                merged_aliases = list(dict.fromkeys([*old_aliases, *aliases]))
                old_meta = json_loads(old["metadata_json"], {})
                merged_meta = {**old_meta, **entity.metadata}
                conn.execute(
                    """
                    UPDATE entities
                    SET entity_type = ?,
                        symbol = ?,
                        aliases_json = ?,
                        last_seen_at = ?,
                        source_count = ?,
                        confidence = ?,
                        metadata_json = ?
                    WHERE canonical_name = ?
                    """,
                    (
                        entity.entity_type or old["entity_type"],
                        entity.symbol or old["symbol"],
                        json_dumps(merged_aliases),
                        now,
                        int(old["source_count"]) + max(1, entity.source_count),
                        max(float(old["confidence"]), float(entity.confidence)),
                        json_dumps(merged_meta),
                        entity.canonical_name,
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO entities (
                        canonical_name, entity_type, symbol, aliases_json, first_seen_at,
                        last_seen_at, source_count, confidence, metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entity.canonical_name,
                        entity.entity_type,
                        entity.symbol,
                        json_dumps(aliases),
                        first_seen,
                        now,
                        max(1, entity.source_count),
                        float(entity.confidence),
                        json_dumps(entity.metadata),
                    ),
                )

    def upsert_relationship(self, rel: RelationshipRecord) -> None:
        now = rel.last_seen_at or utc_now_iso()
        first_seen = rel.first_seen_at or now
        evidence_ids = list(dict.fromkeys(rel.evidence_ids))
        with self.session() as conn:
            old = conn.execute("SELECT * FROM relationships WHERE id = ?", (rel.id,)).fetchone()
            if old:
                old_evidence = json_loads(old["evidence_ids_json"], [])
                merged_evidence = list(dict.fromkeys([*old_evidence, *evidence_ids]))
                old_meta = json_loads(old["metadata_json"], {})
                merged_meta = {**old_meta, **rel.metadata}
                conn.execute(
                    """
                    UPDATE relationships
                    SET confidence = ?,
                        impact_score = ?,
                        recency_score = ?,
                        evidence_count = ?,
                        last_seen_at = ?,
                        evidence_ids_json = ?,
                        metadata_json = ?
                    WHERE id = ?
                    """,
                    (
                        min(1.0, max(float(old["confidence"]), rel.confidence) + 0.03),
                        max(float(old["impact_score"]), float(rel.impact_score)),
                        max(float(old["recency_score"]), float(rel.recency_score)),
                        max(int(old["evidence_count"]) + max(1, rel.evidence_count), len(merged_evidence)),
                        now,
                        json_dumps(merged_evidence),
                        json_dumps(merged_meta),
                        rel.id,
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO relationships (
                        id, source_entity, target_entity, relationship_type, confidence,
                        impact_score, recency_score, evidence_count, first_seen_at, last_seen_at,
                        evidence_ids_json, metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        rel.id,
                        rel.source_entity,
                        rel.target_entity,
                        rel.relationship_type,
                        float(rel.confidence),
                        float(rel.impact_score),
                        float(rel.recency_score),
                        max(1, rel.evidence_count),
                        first_seen,
                        now,
                        json_dumps(evidence_ids),
                        json_dumps(rel.metadata),
                    ),
                )

    def save_hypothesis(self, hypothesis: HypothesisRecord) -> None:
        now = hypothesis.updated_at or utc_now_iso()
        created = hypothesis.created_at or now
        with self.session() as conn:
            old = conn.execute("SELECT id FROM hypotheses WHERE id = ?", (hypothesis.id,)).fetchone()
            if old:
                conn.execute(
                    """
                    UPDATE hypotheses
                    SET title = ?, thesis = ?, status = ?, confidence = ?, symbols_json = ?,
                        themes_json = ?, evidence_ids_json = ?, updated_at = ?, metadata_json = ?
                    WHERE id = ?
                    """,
                    (
                        hypothesis.title,
                        hypothesis.thesis,
                        hypothesis.status,
                        float(hypothesis.confidence),
                        json_dumps(hypothesis.symbols),
                        json_dumps(hypothesis.themes),
                        json_dumps(hypothesis.evidence_ids),
                        now,
                        json_dumps(hypothesis.metadata),
                        hypothesis.id,
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO hypotheses (
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
                        created,
                        now,
                        json_dumps(hypothesis.metadata),
                    ),
                )

    def save_research_run(self, run: ResearchRunRecord) -> None:
        with self.session() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO research_runs (
                    id, run_type, run_path, title, status, started_at, ended_at,
                    metrics_json, symbols_json, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.id,
                    run.run_type,
                    run.run_path,
                    run.title,
                    run.status,
                    run.started_at,
                    run.ended_at,
                    json_dumps(run.metrics),
                    json_dumps(run.symbols),
                    json_dumps(run.metadata),
                ),
            )

    def save_strategy_memory(self, item: StrategyMemoryRecord) -> None:
        with self.session() as conn:
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

    def count_table(self, table: str) -> int:
        allowed = {
            "evidence_items",
            "entities",
            "relationships",
            "hypotheses",
            "research_runs",
            "strategy_memory",
        }
        if table not in allowed:
            raise ValueError(f"Unsupported table: {table}")
        with self.session() as conn:
            return int(conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"])

    def fetch_all(self, table: str, limit: int = 100, order_by: str | None = None) -> list[dict[str, Any]]:
        allowed = {
            "evidence_items": "ingested_at DESC",
            "entities": "source_count DESC, canonical_name ASC",
            "relationships": "confidence DESC, evidence_count DESC, source_entity ASC",
            "hypotheses": "updated_at DESC",
            "research_runs": "ended_at DESC",
            "strategy_memory": "score DESC",
        }
        if table not in allowed:
            raise ValueError(f"Unsupported table: {table}")
        order = order_by or allowed[table]
        with self.session() as conn:
            rows = conn.execute(f"SELECT * FROM {table} ORDER BY {order} LIMIT ?", (int(limit),)).fetchall()
        return [dict(row) for row in rows]

    def summary_counts(self) -> dict[str, int]:
        return {
            "evidence_items": self.count_table("evidence_items"),
            "entities": self.count_table("entities"),
            "relationships": self.count_table("relationships"),
            "hypotheses": self.count_table("hypotheses"),
            "research_runs": self.count_table("research_runs"),
            "strategy_memory": self.count_table("strategy_memory"),
        }
