from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3
from typing import Any
import uuid

from services.database import connect_database, load_database_config, migrate_database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class CatalogArtifact:
    artifact_id: str
    source_path: str
    artifact_type: str | None
    extension: str | None
    sha256: str | None
    size_bytes: int | None


@dataclass
class IngestionSummary:
    run_id: str
    backend: str
    source_catalog_path: str
    artifacts_seen: int = 0
    json_ingested: int = 0
    csv_datasets_ingested: int = 0
    csv_rows_ingested: int = 0
    skipped: int = 0
    errors: int = 0
    status: str = "PASS"


def _repo_root(start: Path) -> Path:
    start = start.resolve()
    for candidate in [start, *start.parents]:
        if (candidate / "Live" / "app.py").exists():
            return candidate
    raise FileNotFoundError(f"Could not find repo root from {start}")


def _catalog_path(repo: Path) -> Path:
    path = repo / "Live" / "data" / "catalog" / "data_catalog.sqlite"
    if not path.exists():
        raise FileNotFoundError(f"Missing catalog database: {path}. Open Data Library and click Rescan Live/data first.")
    return path


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(row[1]) for row in rows}


def _pick(cols: set[str], names: list[str]) -> str | None:
    for name in names:
        if name in cols:
            return name
    return None


def _resolve_path(repo: Path, raw: str) -> Path:
    p = Path(raw)
    if p.is_absolute():
        return p
    for candidate in [repo / raw, repo / "Live" / raw, repo / "Live" / "data" / raw]:
        if candidate.exists():
            return candidate
    return repo / raw


def _artifact_id(path: Path, raw_id: str | None, sha: str | None) -> str:
    return raw_id or sha or hashlib.sha256(str(path).encode("utf-8")).hexdigest()


def _sanitize_json_value(value: Any) -> Any:
    """Return a JSON-safe value for SQLite text or PostgreSQL JSONB.

    Python's json module accepts NaN/Infinity by default, but PostgreSQL JSONB
    rejects those non-standard tokens. This converts non-finite floats to null.
    """
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, dict):
        return {str(key): _sanitize_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_json_value(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_json_value(item) for item in value]
    return value


def _json_dumps_db(value: Any, *, sort_keys: bool = False) -> str:
    return json.dumps(
        _sanitize_json_value(value),
        ensure_ascii=False,
        sort_keys=sort_keys,
        allow_nan=False,
    )


def load_catalog_artifacts(repo_root: str | Path, extensions: set[str] | None = None, limit: int | None = None) -> tuple[Path, list[CatalogArtifact]]:
    repo = _repo_root(Path(repo_root))
    catalog = _catalog_path(repo)
    conn = sqlite3.connect(catalog)
    conn.row_factory = sqlite3.Row
    try:
        cols = _columns(conn, "data_artifacts")
        if not cols:
            raise RuntimeError("data_artifacts table is missing or empty.")

        id_col = _pick(cols, ["artifact_id", "id", "artifact_key"])
        path_col = _pick(cols, ["file_path", "path", "relative_path", "absolute_path", "source_path", "artifact_path"])
        name_col = _pick(cols, ["file_name", "filename", "name"])
        type_col = _pick(cols, ["artifact_type", "type", "category"])
        ext_col = _pick(cols, ["extension", "file_extension", "suffix"])
        sha_col = _pick(cols, ["sha256", "content_sha256", "file_sha256"])
        size_col = _pick(cols, ["size_bytes", "file_size_bytes", "bytes"])

        if not path_col and not name_col:
            raise RuntimeError(f"Could not identify a file path column. data_artifacts columns: {sorted(cols)}")

        selected = []
        for col in [id_col, path_col, name_col, type_col, ext_col, sha_col, size_col]:
            if col and col not in selected:
                selected.append(col)

        sql = f"SELECT {', '.join(selected)} FROM data_artifacts ORDER BY rowid DESC"
        params: list[Any] = []
        if limit:
            sql += " LIMIT ?"
            params.append(int(limit))

        artifacts: list[CatalogArtifact] = []
        for row in conn.execute(sql, params).fetchall():
            raw_path = str(row[path_col]) if path_col and row[path_col] is not None else str(row[name_col])
            path = _resolve_path(repo, raw_path)
            ext = str(row[ext_col]).lower().lstrip(".") if ext_col and row[ext_col] is not None else path.suffix.lower().lstrip(".")
            if extensions and ext not in extensions:
                continue
            raw_id = str(row[id_col]) if id_col and row[id_col] is not None else None
            sha = str(row[sha_col]) if sha_col and row[sha_col] is not None else None
            size = int(row[size_col]) if size_col and row[size_col] is not None else (path.stat().st_size if path.exists() else None)
            artifacts.append(
                CatalogArtifact(
                    artifact_id=_artifact_id(path, raw_id, sha),
                    source_path=str(path),
                    artifact_type=str(row[type_col]) if type_col and row[type_col] is not None else None,
                    extension=ext,
                    sha256=sha,
                    size_bytes=size,
                )
            )
        return catalog, artifacts
    finally:
        conn.close()


def _execute(db, sql: str, params: tuple[Any, ...] = ()) -> None:
    cur = db.cursor()
    try:
        cur.execute(sql, params)
    finally:
        cur.close()


def _upsert_artifact(db, artifact: CatalogArtifact, status: str, reason: str | None) -> None:
    now = _now()
    if db.backend == "postgres":
        sql = """INSERT INTO db_ingested_artifacts
        (artifact_id, source_path, artifact_type, extension, sha256, size_bytes, ingested_backend, ingested_at, status, skip_reason)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (artifact_id) DO UPDATE SET
        source_path=EXCLUDED.source_path, artifact_type=EXCLUDED.artifact_type, extension=EXCLUDED.extension,
        sha256=EXCLUDED.sha256, size_bytes=EXCLUDED.size_bytes, ingested_backend=EXCLUDED.ingested_backend,
        ingested_at=EXCLUDED.ingested_at, status=EXCLUDED.status, skip_reason=EXCLUDED.skip_reason"""
    else:
        sql = """INSERT OR REPLACE INTO db_ingested_artifacts
        (artifact_id, source_path, artifact_type, extension, sha256, size_bytes, ingested_backend, ingested_at, status, skip_reason)
        VALUES (?,?,?,?,?,?,?,?,?,?)"""
    _execute(db, sql, (artifact.artifact_id, artifact.source_path, artifact.artifact_type, artifact.extension, artifact.sha256, artifact.size_bytes, db.backend, now, status, reason))


def _ingest_json(db, artifact: CatalogArtifact, max_json_bytes: int) -> bool:
    path = Path(artifact.source_path)
    if not path.exists():
        _upsert_artifact(db, artifact, "skipped", "file_missing")
        return False
    size = path.stat().st_size
    if size > max_json_bytes:
        _upsert_artifact(db, artifact, "skipped", f"json_too_large:{size}>{max_json_bytes}")
        return False

    payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    payload_text = _json_dumps_db(payload, sort_keys=True)
    now = _now()
    if db.backend == "postgres":
        sql = """INSERT INTO db_json_payloads (artifact_id, source_path, payload_json, payload_size_bytes, root_type, ingested_at)
        VALUES (%s,%s,%s::jsonb,%s,%s,%s)
        ON CONFLICT (artifact_id) DO UPDATE SET source_path=EXCLUDED.source_path, payload_json=EXCLUDED.payload_json,
        payload_size_bytes=EXCLUDED.payload_size_bytes, root_type=EXCLUDED.root_type, ingested_at=EXCLUDED.ingested_at"""
    else:
        sql = """INSERT OR REPLACE INTO db_json_payloads (artifact_id, source_path, payload_json, payload_size_bytes, root_type, ingested_at)
        VALUES (?,?,?,?,?,?)"""
    _execute(db, sql, (artifact.artifact_id, artifact.source_path, payload_text, len(payload_text.encode("utf-8")), type(payload).__name__, now))
    _upsert_artifact(db, artifact, "ingested", None)
    return True


def _dialect(path: Path):
    try:
        sample = path.read_text(encoding="utf-8", errors="replace")[:4096]
        return csv.Sniffer().sniff(sample)
    except Exception:
        return csv.excel


def _ingest_csv(db, artifact: CatalogArtifact, max_csv_rows: int) -> tuple[bool, int]:
    path = Path(artifact.source_path)
    if not path.exists():
        _upsert_artifact(db, artifact, "skipped", "file_missing")
        return False, 0

    now = _now()
    dialect = _dialect(path)
    delete_sql = "DELETE FROM db_csv_rows WHERE artifact_id = %s" if db.backend == "postgres" else "DELETE FROM db_csv_rows WHERE artifact_id = ?"
    _execute(db, delete_sql, (artifact.artifact_id,))

    if db.backend == "postgres":
        row_sql = "INSERT INTO db_csv_rows (artifact_id, row_number, row_json, ingested_at) VALUES (%s,%s,%s::jsonb,%s)"
        dataset_sql = """INSERT INTO db_csv_datasets (artifact_id, source_path, delimiter, header_json, row_count_total, rows_ingested, truncated, ingested_at)
        VALUES (%s,%s,%s,%s::jsonb,%s,%s,%s,%s)
        ON CONFLICT (artifact_id) DO UPDATE SET source_path=EXCLUDED.source_path, delimiter=EXCLUDED.delimiter,
        header_json=EXCLUDED.header_json, row_count_total=EXCLUDED.row_count_total, rows_ingested=EXCLUDED.rows_ingested,
        truncated=EXCLUDED.truncated, ingested_at=EXCLUDED.ingested_at"""
    else:
        row_sql = "INSERT OR REPLACE INTO db_csv_rows (artifact_id, row_number, row_json, ingested_at) VALUES (?,?,?,?)"
        dataset_sql = """INSERT OR REPLACE INTO db_csv_datasets (artifact_id, source_path, delimiter, header_json, row_count_total, rows_ingested, truncated, ingested_at)
        VALUES (?,?,?,?,?,?,?,?)"""

    total = 0
    stored = 0
    headers: list[str] = []
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle, dialect=dialect)
        headers = list(reader.fieldnames or [])
        for row in reader:
            total += 1
            if stored < max_csv_rows:
                row_json = _json_dumps_db({str(k): v for k, v in row.items()})
                _execute(db, row_sql, (artifact.artifact_id, total, row_json, now))
                stored += 1

    truncated = stored < total
    _execute(db, dataset_sql, (artifact.artifact_id, artifact.source_path, getattr(dialect, "delimiter", ","), _json_dumps_db(headers), total, stored, truncated, now))
    _upsert_artifact(db, artifact, "ingested", "csv_truncated" if truncated else None)
    return True, stored


def _create_run(db, summary: IngestionSummary, max_json_bytes: int, max_csv_rows: int) -> None:
    if db.backend == "postgres":
        sql = """INSERT INTO db_ingestion_runs (run_id, backend, started_at, status, source_catalog_path, max_json_bytes, max_csv_rows)
        VALUES (%s,%s,%s,%s,%s,%s,%s)"""
    else:
        sql = """INSERT INTO db_ingestion_runs (run_id, backend, started_at, status, source_catalog_path, max_json_bytes, max_csv_rows)
        VALUES (?,?,?,?,?,?,?)"""
    _execute(db, sql, (summary.run_id, summary.backend, _now(), "running", summary.source_catalog_path, max_json_bytes, max_csv_rows))


def _finish_run(db, summary: IngestionSummary, error_message: str | None = None) -> None:
    summary.status = "PASS" if summary.errors == 0 and error_message is None else "FAIL"
    if db.backend == "postgres":
        sql = """UPDATE db_ingestion_runs SET finished_at=%s, status=%s, artifacts_seen=%s, json_ingested=%s,
        csv_datasets_ingested=%s, csv_rows_ingested=%s, skipped=%s, errors=%s, error_message=%s WHERE run_id=%s"""
    else:
        sql = """UPDATE db_ingestion_runs SET finished_at=?, status=?, artifacts_seen=?, json_ingested=?,
        csv_datasets_ingested=?, csv_rows_ingested=?, skipped=?, errors=?, error_message=? WHERE run_id=?"""
    _execute(db, sql, (_now(), summary.status, summary.artifacts_seen, summary.json_ingested, summary.csv_datasets_ingested, summary.csv_rows_ingested, summary.skipped, summary.errors, error_message, summary.run_id))


def ingest_catalog_to_database(repo_root: str | Path, backend: str | None = None, max_json_bytes: int = 5 * 1024 * 1024, max_csv_rows: int = 5000, limit: int | None = None) -> IngestionSummary:
    repo = _repo_root(Path(repo_root))
    catalog, artifacts = load_catalog_artifacts(repo, extensions={"json", "csv"}, limit=limit)
    config = load_database_config(repo_root=repo, backend=backend)

    with connect_database(config) as db:
        migrate_database(db)
        summary = IngestionSummary(run_id=str(uuid.uuid4()), backend=db.backend, source_catalog_path=str(catalog))
        _create_run(db, summary, max_json_bytes, max_csv_rows)
        db.commit()

        for artifact in artifacts:
            summary.artifacts_seen += 1
            try:
                ext = (artifact.extension or "").lower().lstrip(".")
                if ext == "json":
                    if _ingest_json(db, artifact, max_json_bytes):
                        summary.json_ingested += 1
                    else:
                        summary.skipped += 1
                elif ext == "csv":
                    ok, rows = _ingest_csv(db, artifact, max_csv_rows)
                    if ok:
                        summary.csv_datasets_ingested += 1
                        summary.csv_rows_ingested += rows
                    else:
                        summary.skipped += 1
                else:
                    _upsert_artifact(db, artifact, "skipped", "unsupported_extension")
                    summary.skipped += 1
                db.commit()
            except Exception as exc:
                db.rollback()
                summary.errors += 1
                summary.skipped += 1
                reason = f"error:{type(exc).__name__}:{exc}"
                try:
                    _upsert_artifact(db, artifact, "skipped", reason[:2000])
                    db.commit()
                except Exception:
                    db.rollback()

        _finish_run(db, summary)
        db.commit()
        return summary
