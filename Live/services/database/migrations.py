from __future__ import annotations

from .backend import DatabaseConnection


SQLITE_TABLES = [
    """CREATE TABLE IF NOT EXISTS db_ingestion_runs (
        run_id TEXT PRIMARY KEY,
        backend TEXT NOT NULL,
        started_at TEXT NOT NULL,
        finished_at TEXT,
        status TEXT NOT NULL,
        source_catalog_path TEXT,
        max_json_bytes INTEGER,
        max_csv_rows INTEGER,
        artifacts_seen INTEGER DEFAULT 0,
        json_ingested INTEGER DEFAULT 0,
        csv_datasets_ingested INTEGER DEFAULT 0,
        csv_rows_ingested INTEGER DEFAULT 0,
        skipped INTEGER DEFAULT 0,
        errors INTEGER DEFAULT 0,
        error_message TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS db_ingested_artifacts (
        artifact_id TEXT PRIMARY KEY,
        source_path TEXT NOT NULL,
        artifact_type TEXT,
        extension TEXT,
        sha256 TEXT,
        size_bytes INTEGER,
        ingested_backend TEXT NOT NULL,
        ingested_at TEXT NOT NULL,
        status TEXT NOT NULL,
        skip_reason TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS db_json_payloads (
        artifact_id TEXT PRIMARY KEY,
        source_path TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        payload_size_bytes INTEGER NOT NULL,
        root_type TEXT,
        ingested_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS db_csv_datasets (
        artifact_id TEXT PRIMARY KEY,
        source_path TEXT NOT NULL,
        delimiter TEXT,
        header_json TEXT,
        row_count_total INTEGER,
        rows_ingested INTEGER,
        truncated INTEGER DEFAULT 0,
        ingested_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS db_csv_rows (
        artifact_id TEXT NOT NULL,
        row_number INTEGER NOT NULL,
        row_json TEXT NOT NULL,
        ingested_at TEXT NOT NULL,
        PRIMARY KEY (artifact_id, row_number)
    )""",
]

POSTGRES_TABLES = [
    """CREATE TABLE IF NOT EXISTS db_ingestion_runs (
        run_id TEXT PRIMARY KEY,
        backend TEXT NOT NULL,
        started_at TIMESTAMPTZ NOT NULL,
        finished_at TIMESTAMPTZ,
        status TEXT NOT NULL,
        source_catalog_path TEXT,
        max_json_bytes BIGINT,
        max_csv_rows BIGINT,
        artifacts_seen BIGINT DEFAULT 0,
        json_ingested BIGINT DEFAULT 0,
        csv_datasets_ingested BIGINT DEFAULT 0,
        csv_rows_ingested BIGINT DEFAULT 0,
        skipped BIGINT DEFAULT 0,
        errors BIGINT DEFAULT 0,
        error_message TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS db_ingested_artifacts (
        artifact_id TEXT PRIMARY KEY,
        source_path TEXT NOT NULL,
        artifact_type TEXT,
        extension TEXT,
        sha256 TEXT,
        size_bytes BIGINT,
        ingested_backend TEXT NOT NULL,
        ingested_at TIMESTAMPTZ NOT NULL,
        status TEXT NOT NULL,
        skip_reason TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS db_json_payloads (
        artifact_id TEXT PRIMARY KEY,
        source_path TEXT NOT NULL,
        payload_json JSONB NOT NULL,
        payload_size_bytes BIGINT NOT NULL,
        root_type TEXT,
        ingested_at TIMESTAMPTZ NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS db_csv_datasets (
        artifact_id TEXT PRIMARY KEY,
        source_path TEXT NOT NULL,
        delimiter TEXT,
        header_json JSONB,
        row_count_total BIGINT,
        rows_ingested BIGINT,
        truncated BOOLEAN DEFAULT FALSE,
        ingested_at TIMESTAMPTZ NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS db_csv_rows (
        artifact_id TEXT NOT NULL,
        row_number BIGINT NOT NULL,
        row_json JSONB NOT NULL,
        ingested_at TIMESTAMPTZ NOT NULL,
        PRIMARY KEY (artifact_id, row_number)
    )""",
]


def migrate_database(db: DatabaseConnection) -> None:
    cur = db.cursor()
    try:
        for sql in (POSTGRES_TABLES if db.backend == "postgres" else SQLITE_TABLES):
            cur.execute(sql)
        db.commit()
    finally:
        cur.close()
