from __future__ import annotations

from pathlib import Path
import sqlite3
from contextlib import contextmanager
from typing import Iterator

from .models import dumps, utc_now_iso


SCHEMA = [
"""
CREATE TABLE IF NOT EXISTS data_artifacts (
  artifact_id TEXT PRIMARY KEY,
  artifact_type TEXT NOT NULL,
  file_path TEXT NOT NULL UNIQUE,
  file_name TEXT NOT NULL,
  extension TEXT NOT NULL,
  size_bytes INTEGER NOT NULL DEFAULT 0,
  sha256 TEXT NOT NULL,
  created_at TEXT,
  modified_at TEXT,
  indexed_at TEXT NOT NULL,
  source_module TEXT,
  symbol TEXT,
  theme TEXT,
  strategy_family TEXT,
  run_id TEXT,
  tags_json TEXT NOT NULL DEFAULT '[]',
  metadata_json TEXT NOT NULL DEFAULT '{}'
)
""",
"CREATE INDEX IF NOT EXISTS idx_data_artifacts_type ON data_artifacts(artifact_type)",
"CREATE INDEX IF NOT EXISTS idx_data_artifacts_ext ON data_artifacts(extension)",
"CREATE INDEX IF NOT EXISTS idx_data_artifacts_symbol ON data_artifacts(symbol)",
"""
CREATE TABLE IF NOT EXISTS artifact_json_payloads (
  artifact_id TEXT PRIMARY KEY,
  json_kind TEXT,
  top_level_keys_json TEXT NOT NULL DEFAULT '[]',
  preview_json TEXT NOT NULL DEFAULT '{}',
  payload_status TEXT NOT NULL DEFAULT 'preview_only',
  error TEXT
)
""",
"""
CREATE TABLE IF NOT EXISTS artifact_csv_datasets (
  artifact_id TEXT PRIMARY KEY,
  delimiter TEXT,
  headers_json TEXT NOT NULL DEFAULT '[]',
  row_count INTEGER NOT NULL DEFAULT 0,
  column_count INTEGER NOT NULL DEFAULT 0,
  sample_rows_json TEXT NOT NULL DEFAULT '[]',
  payload_status TEXT NOT NULL DEFAULT 'preview_only',
  error TEXT
)
""",
"""
CREATE TABLE IF NOT EXISTS artifact_csv_rows (
  artifact_id TEXT NOT NULL,
  row_number INTEGER NOT NULL,
  row_json TEXT NOT NULL,
  PRIMARY KEY(artifact_id, row_number)
)
""",
"""
CREATE TABLE IF NOT EXISTS markdown_documents (
  artifact_id TEXT PRIMARY KEY,
  title TEXT,
  headings_json TEXT NOT NULL DEFAULT '[]',
  preview_text TEXT,
  word_count INTEGER NOT NULL DEFAULT 0,
  line_count INTEGER NOT NULL DEFAULT 0
)
""",
"""
CREATE TABLE IF NOT EXISTS experiment_runs (
  run_id TEXT PRIMARY KEY,
  artifact_id TEXT,
  run_type TEXT,
  symbol TEXT,
  strategy_family TEXT,
  started_at TEXT,
  completed_at TEXT,
  metrics_json TEXT NOT NULL DEFAULT '{}',
  metadata_json TEXT NOT NULL DEFAULT '{}'
)
""",
"""
CREATE TABLE IF NOT EXISTS strategy_registry (
  strategy_id TEXT PRIMARY KEY,
  strategy_family TEXT NOT NULL,
  strategy_name TEXT,
  module_path TEXT,
  parameters_json TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'candidate',
  created_at TEXT,
  updated_at TEXT
)
""",
"""
CREATE TABLE IF NOT EXISTS symbol_universe_snapshots (
  snapshot_id TEXT PRIMARY KEY,
  universe_name TEXT NOT NULL,
  symbols_json TEXT NOT NULL DEFAULT '[]',
  source_artifact_id TEXT,
  created_at TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}'
)
""",
"""
CREATE TABLE IF NOT EXISTS data_catalog_scan_runs (
  run_id TEXT PRIMARY KEY,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  status TEXT NOT NULL,
  root_path TEXT NOT NULL,
  files_seen INTEGER NOT NULL DEFAULT 0,
  files_indexed INTEGER NOT NULL DEFAULT 0,
  files_skipped INTEGER NOT NULL DEFAULT 0,
  artifact_type_counts_json TEXT NOT NULL DEFAULT '{}',
  errors_json TEXT NOT NULL DEFAULT '[]'
)
""",
]


def default_data_catalog_paths(live_root: Path) -> dict[str, Path]:
    root = Path(live_root) / "data" / "catalog"
    return {"catalog_dir": root, "db_path": root / "data_catalog.sqlite"}


class DataCatalogStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    @contextmanager
    def session(self) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def initialize(self) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            for stmt in SCHEMA:
                conn.execute(stmt)
            conn.commit()

    def upsert_artifact(self, row: dict) -> None:
        cols = [
            "artifact_id", "artifact_type", "file_path", "file_name", "extension",
            "size_bytes", "sha256", "created_at", "modified_at", "indexed_at",
            "source_module", "symbol", "theme", "strategy_family", "run_id",
            "tags_json", "metadata_json",
        ]
        updates = ",".join(f"{c}=excluded.{c}" for c in cols if c != "artifact_id")
        with self.session() as conn:
            conn.execute(
                f"INSERT INTO data_artifacts ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)}) "
                f"ON CONFLICT(artifact_id) DO UPDATE SET {updates}",
                [row.get(c, "") for c in cols],
            )

    def upsert_json_preview(self, artifact_id: str, kind: str, keys: list[str], preview, error: str = "") -> None:
        with self.session() as conn:
            conn.execute(
                """
                INSERT INTO artifact_json_payloads VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(artifact_id) DO UPDATE SET
                json_kind=excluded.json_kind,
                top_level_keys_json=excluded.top_level_keys_json,
                preview_json=excluded.preview_json,
                payload_status=excluded.payload_status,
                error=excluded.error
                """,
                [artifact_id, kind, dumps(keys), dumps(preview), "preview_only", error],
            )

    def upsert_csv_preview(self, artifact_id: str, headers: list[str], rows: int, cols: int, sample: list[dict], error: str = "") -> None:
        with self.session() as conn:
            conn.execute(
                """
                INSERT INTO artifact_csv_datasets VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(artifact_id) DO UPDATE SET
                headers_json=excluded.headers_json,
                row_count=excluded.row_count,
                column_count=excluded.column_count,
                sample_rows_json=excluded.sample_rows_json,
                payload_status=excluded.payload_status,
                error=excluded.error
                """,
                [artifact_id, ",", dumps(headers), int(rows), int(cols), dumps(sample), "preview_only", error],
            )

    def upsert_markdown(self, artifact_id: str, doc: dict) -> None:
        with self.session() as conn:
            conn.execute(
                """
                INSERT INTO markdown_documents VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(artifact_id) DO UPDATE SET
                title=excluded.title,
                headings_json=excluded.headings_json,
                preview_text=excluded.preview_text,
                word_count=excluded.word_count,
                line_count=excluded.line_count
                """,
                [
                    artifact_id,
                    doc.get("title", ""),
                    dumps(doc.get("headings", [])),
                    doc.get("preview_text", ""),
                    int(doc.get("word_count", 0)),
                    int(doc.get("line_count", 0)),
                ],
            )

    def record_scan(self, result: dict) -> None:
        with self.session() as conn:
            conn.execute(
                """
                INSERT INTO data_catalog_scan_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                completed_at=excluded.completed_at,
                status=excluded.status,
                files_seen=excluded.files_seen,
                files_indexed=excluded.files_indexed,
                files_skipped=excluded.files_skipped,
                artifact_type_counts_json=excluded.artifact_type_counts_json,
                errors_json=excluded.errors_json
                """,
                [
                    result["run_id"], result["started_at"], result["completed_at"],
                    result["status"], result["root_path"], result["files_seen"],
                    result["files_indexed"], result["files_skipped"],
                    dumps(result["artifact_type_counts"]), dumps(result["errors"]),
                ],
            )

    def counts(self) -> dict[str, int]:
        tables = [
            "data_artifacts", "artifact_json_payloads", "artifact_csv_datasets",
            "artifact_csv_rows", "markdown_documents", "experiment_runs",
            "strategy_registry", "symbol_universe_snapshots", "data_catalog_scan_runs",
        ]
        out = {}
        with self.session() as conn:
            for table in tables:
                out[table] = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        return out

    def health(self) -> dict:
        return {"db_path": str(self.db_path), "checked_at": utc_now_iso(), "counts": self.counts()}
