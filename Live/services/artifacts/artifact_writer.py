from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import csv, hashlib, json, math, os, re, sqlite3, uuid
from pathlib import Path
from typing import Any


@dataclass
class ArtifactResult:
    artifact_id: str
    path: str
    relative_path: str
    extension: str
    module: str
    artifact_type: str
    symbol: str | None
    theme: str | None
    tags: list[str]
    sha256: str
    size_bytes: int
    created_at: str
    registry_status: str = "registered"
    db_status: str = "not_attempted"
    db_error: str | None = None
    pending: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def repo_root(start: str | Path | None = None) -> Path:
    p = Path(start or Path.cwd()).resolve()
    for c in [p, *p.parents]:
        if (c / "Live" / "app.py").exists():
            return c
        if c.name.lower() == "live" and (c / "app.py").exists():
            return c.parent
    raise FileNotFoundError(f"Could not find repo root from {p}")


def slug(v: Any, fallback: str = "artifact") -> str:
    s = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(v or "").strip()).strip("._-")
    return (s or fallback)[:80]


def tags_list(tags: Any = None) -> list[str]:
    if tags is None:
        return []
    if isinstance(tags, str):
        return [x.strip() for x in tags.split(",") if x.strip()]
    try:
        return [str(x).strip() for x in tags if str(x).strip()]
    except Exception:
        return [str(tags).strip()]


def json_safe(v: Any) -> Any:
    if isinstance(v, float):
        return None if math.isnan(v) or math.isinf(v) else v
    if isinstance(v, dict):
        return {str(k): json_safe(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [json_safe(x) for x in v]
    return v


def dumps(v: Any, sort_keys: bool = False) -> str:
    return json.dumps(json_safe(v), ensure_ascii=False, allow_nan=False, sort_keys=sort_keys, default=str)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def registry_path(root: Path) -> Path:
    p = root / "Live" / "data" / "catalog" / "artifact_writer.sqlite"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def registry(root: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(registry_path(root))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""CREATE TABLE IF NOT EXISTS managed_artifacts(
        artifact_id TEXT PRIMARY KEY, path TEXT, relative_path TEXT, extension TEXT,
        module TEXT, artifact_type TEXT, symbol TEXT, theme TEXT, tags_json TEXT,
        sha256 TEXT, size_bytes INTEGER, created_at TEXT, registry_status TEXT,
        db_status TEXT, db_error TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS pending_artifact_ingestion(
        artifact_id TEXT PRIMARY KEY, path TEXT, relative_path TEXT, extension TEXT,
        module TEXT, artifact_type TEXT, symbol TEXT, theme TEXT, tags_json TEXT,
        sha256 TEXT, size_bytes INTEGER, created_at TEXT, retries INTEGER DEFAULT 0,
        last_error TEXT, updated_at TEXT)""")
    conn.commit()
    return conn


def rel(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except Exception:
        return str(path)


def upsert_registry(root: Path, r: ArtifactResult) -> None:
    with registry(root) as conn:
        conn.execute("""INSERT OR REPLACE INTO managed_artifacts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (r.artifact_id, r.path, r.relative_path, r.extension, r.module, r.artifact_type,
             r.symbol, r.theme, dumps(r.tags), r.sha256, r.size_bytes, r.created_at,
             r.registry_status, r.db_status, r.db_error))
        conn.commit()


def queue_pending(root: Path, r: ArtifactResult, err: str) -> None:
    with registry(root) as conn:
        conn.execute("""INSERT INTO pending_artifact_ingestion
            (artifact_id,path,relative_path,extension,module,artifact_type,symbol,theme,tags_json,sha256,size_bytes,created_at,retries,last_error,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(artifact_id) DO UPDATE SET
              retries=pending_artifact_ingestion.retries+1,last_error=excluded.last_error,updated_at=excluded.updated_at""",
            (r.artifact_id, r.path, r.relative_path, r.extension, r.module, r.artifact_type,
             r.symbol, r.theme, dumps(r.tags), r.sha256, r.size_bytes, r.created_at, 0, err, utc_now()))
        conn.commit()


def clear_pending(root: Path, artifact_id: str) -> None:
    with registry(root) as conn:
        conn.execute("DELETE FROM pending_artifact_ingestion WHERE artifact_id=?", (artifact_id,))
        conn.commit()


def should_ingest(ingest: bool | None) -> bool:
    if ingest is False:
        return False
    flag = os.environ.get("ALGOTRADER_ARTIFACT_POSTGRES_INGEST")
    if flag is not None:
        return flag.lower().strip() in {"1", "true", "yes", "on"}
    return os.environ.get("ALGOTRADER_DB_BACKEND", "").lower() in {"postgres", "postgresql"} or bool(os.environ.get("ALGOTRADER_DB_PASSWORD") or os.environ.get("ALGOTRADER_DATABASE_URL"))


def make_path(root: Path, module: str, artifact_type: str, ext: str, symbol=None, theme=None, prefix=None) -> tuple[str, Path]:
    artifact_id = hashlib.sha256(f"{module}|{artifact_type}|{symbol}|{theme}|{utc_now()}|{uuid.uuid4()}".encode()).hexdigest()[:24]
    day = utc_now()[:10]
    base = root / "Live" / "data" / "managed_artifacts" / slug(module, "module") / slug(artifact_type, "artifact") / day
    base.mkdir(parents=True, exist_ok=True)
    stem = "_".join([x for x in [utc_now().replace(":", "").replace("+", "Z"), slug(prefix, "") if prefix else "", slug(symbol, "") if symbol else "", slug(theme, "") if theme else "", artifact_id] if x])
    return artifact_id, base / f"{stem}.{ext}"


def db_parts():
    from services.database.config import load_database_config
    try:
        from services.database.backend import connect_database
    except Exception:
        from services.database.connections import connect_database  # type: ignore
    from services.database.migrations import migrate_database
    return load_database_config, connect_database, migrate_database


def cur(db):
    return db.cursor() if hasattr(db, "cursor") else db.conn.cursor()


def commit(db):
    return db.commit() if hasattr(db, "commit") else db.conn.commit()


def rollback(db):
    try:
        return db.rollback() if hasattr(db, "rollback") else db.conn.rollback()
    except Exception:
        return None


def backend(db) -> str:
    return str(getattr(db, "backend", "postgres")).lower()


def exe(db, sql: str, params=()):
    c = cur(db)
    try:
        c.execute(sql, params)
    finally:
        c.close()


def upsert_db_meta(db, r: ArtifactResult, status: str, reason: str | None):
    if backend(db) == "postgres":
        sql = """INSERT INTO db_ingested_artifacts
        (artifact_id,source_path,artifact_type,extension,sha256,size_bytes,ingested_backend,ingested_at,status,skip_reason)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (artifact_id) DO UPDATE SET source_path=EXCLUDED.source_path,artifact_type=EXCLUDED.artifact_type,
        extension=EXCLUDED.extension,sha256=EXCLUDED.sha256,size_bytes=EXCLUDED.size_bytes,ingested_backend=EXCLUDED.ingested_backend,
        ingested_at=EXCLUDED.ingested_at,status=EXCLUDED.status,skip_reason=EXCLUDED.skip_reason"""
    else:
        sql = """INSERT OR REPLACE INTO db_ingested_artifacts
        (artifact_id,source_path,artifact_type,extension,sha256,size_bytes,ingested_backend,ingested_at,status,skip_reason)
        VALUES (?,?,?,?,?,?,?,?,?,?)"""
    exe(db, sql, (r.artifact_id, r.path, r.artifact_type, r.extension, r.sha256, r.size_bytes, backend(db), utc_now(), status, reason))


def ingest_to_db(r: ArtifactResult, root: str | Path | None = None, max_json_bytes: int | None = None, max_csv_rows: int | None = None) -> ArtifactResult:
    rootp = repo_root(root)
    max_json_bytes = int(max_json_bytes or os.environ.get("ALGOTRADER_MAX_JSON_BYTES") or 5 * 1024 * 1024)
    max_csv_rows = int(max_csv_rows or os.environ.get("ALGOTRADER_MAX_CSV_ROWS") or 5000)
    load_config, connect_db, migrate_db = db_parts()
    cfg = load_config(repo_root=str(rootp), backend="postgres")
    with connect_db(cfg) as db:
        migrate_db(db)
        try:
            ext = r.extension.lower()
            path = Path(r.path)
            if ext == "json" and r.size_bytes <= max_json_bytes:
                payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
                txt = dumps(payload, sort_keys=True)
                if backend(db) == "postgres":
                    sql = """INSERT INTO db_json_payloads VALUES (%s,%s,%s::jsonb,%s,%s,%s)
                    ON CONFLICT (artifact_id) DO UPDATE SET source_path=EXCLUDED.source_path,payload_json=EXCLUDED.payload_json,
                    payload_size_bytes=EXCLUDED.payload_size_bytes,root_type=EXCLUDED.root_type,ingested_at=EXCLUDED.ingested_at"""
                else:
                    sql = "INSERT OR REPLACE INTO db_json_payloads VALUES (?,?,?,?,?,?)"
                exe(db, sql, (r.artifact_id, r.path, txt, len(txt.encode()), type(payload).__name__, utc_now()))
                upsert_db_meta(db, r, "ingested", None)
                r.db_status, r.db_error = "ingested", None
            elif ext == "csv":
                rows, total, headers = [], 0, []
                with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
                    reader = csv.DictReader(f)
                    headers = list(reader.fieldnames or [])
                    for row in reader:
                        total += 1
                        if len(rows) < max_csv_rows:
                            rows.append({str(k): v for k, v in row.items()})
                if backend(db) == "postgres":
                    exe(db, "DELETE FROM db_csv_rows WHERE artifact_id=%s", (r.artifact_id,))
                    row_sql = "INSERT INTO db_csv_rows VALUES (%s,%s,%s::jsonb,%s)"
                    ds_sql = """INSERT INTO db_csv_datasets VALUES (%s,%s,%s,%s::jsonb,%s,%s,%s,%s)
                    ON CONFLICT (artifact_id) DO UPDATE SET source_path=EXCLUDED.source_path,delimiter=EXCLUDED.delimiter,
                    header_json=EXCLUDED.header_json,row_count_total=EXCLUDED.row_count_total,rows_ingested=EXCLUDED.rows_ingested,
                    truncated=EXCLUDED.truncated,ingested_at=EXCLUDED.ingested_at"""
                else:
                    exe(db, "DELETE FROM db_csv_rows WHERE artifact_id=?", (r.artifact_id,))
                    row_sql = "INSERT OR REPLACE INTO db_csv_rows VALUES (?,?,?,?)"
                    ds_sql = "INSERT OR REPLACE INTO db_csv_datasets VALUES (?,?,?,?,?,?,?,?)"
                for i, row in enumerate(rows, 1):
                    exe(db, row_sql, (r.artifact_id, i, dumps(row), utc_now()))
                exe(db, ds_sql, (r.artifact_id, r.path, ",", dumps(headers), total, len(rows), len(rows) < total, utc_now()))
                upsert_db_meta(db, r, "ingested", "csv_truncated" if len(rows) < total else None)
                r.db_status, r.db_error = "ingested", ("csv_truncated" if len(rows) < total else None)
            else:
                upsert_db_meta(db, r, "metadata_only", "content_not_ingested")
                r.db_status, r.db_error = "metadata_only", "content_not_ingested"
            commit(db)
            clear_pending(rootp, r.artifact_id)
            upsert_registry(rootp, r)
            return r
        except Exception:
            rollback(db)
            raise


def finalize(root: Path, artifact_id: str, path: Path, ext: str, module: str, artifact_type: str, symbol, theme, tags, ingest) -> ArtifactResult:
    r = ArtifactResult(artifact_id, str(path), rel(root, path), ext, module, artifact_type, symbol, theme, tags_list(tags), sha256_file(path), path.stat().st_size, utc_now())
    if should_ingest(ingest):
        try:
            r = ingest_to_db(r, root=root)
        except Exception as e:
            r.db_status, r.db_error, r.pending = "pending", f"{type(e).__name__}: {e}", True
            queue_pending(root, r, r.db_error)
    else:
        r.db_status, r.db_error = "skipped", "database_ingest_not_enabled"
    upsert_registry(root, r)
    return r


def save_json(*, module: str, artifact_type: str, payload: Any, symbol=None, theme=None, tags=None, filename_prefix=None, repo_root: str | Path | None = None, ingest: bool | None = True) -> ArtifactResult:
    root = globals()["repo_root"](repo_root)
    aid, path = make_path(root, module, artifact_type, "json", symbol, theme, filename_prefix)
    path.write_text(dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    return finalize(root, aid, path, "json", module, artifact_type, symbol, theme, tags, ingest)


def save_csv(*, module: str, artifact_type: str, rows: list[dict[str, Any]] | None = None, dataframe: Any = None, symbol=None, theme=None, tags=None, filename_prefix=None, repo_root: str | Path | None = None, ingest: bool | None = True) -> ArtifactResult:
    root = globals()["repo_root"](repo_root)
    aid, path = make_path(root, module, artifact_type, "csv", symbol, theme, filename_prefix)
    if dataframe is not None:
        try:
            dataframe.to_csv(path, index=False)
        except TypeError:
            dataframe.to_csv(path)
    else:
        rows = rows or []
        fields = []
        for row in rows:
            for k in row:
                k = str(k)
                if k not in fields:
                    fields.append(k)
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for row in rows:
                w.writerow({k: row.get(k, "") for k in fields})
    return finalize(root, aid, path, "csv", module, artifact_type, symbol, theme, tags, ingest)


def save_markdown(*, module: str, artifact_type: str, markdown: str, symbol=None, theme=None, tags=None, filename_prefix=None, repo_root: str | Path | None = None, ingest: bool | None = True) -> ArtifactResult:
    root = globals()["repo_root"](repo_root)
    aid, path = make_path(root, module, artifact_type, "md", symbol, theme, filename_prefix)
    path.write_text(str(markdown).rstrip() + "\n", encoding="utf-8")
    return finalize(root, aid, path, "md", module, artifact_type, symbol, theme, tags, ingest)


def register_existing_file(*, path: str | Path, module: str, artifact_type: str, symbol=None, theme=None, tags=None, repo_root: str | Path | None = None, ingest: bool | None = True) -> ArtifactResult:
    root = globals()["repo_root"](repo_root)
    p = Path(path)
    if not p.is_absolute():
        p = root / p
    if not p.exists():
        raise FileNotFoundError(p)
    aid = hashlib.sha256(f"{p}|{utc_now()}|{uuid.uuid4()}".encode()).hexdigest()[:24]
    return finalize(root, aid, p, p.suffix.lower().lstrip(".") or "bin", module, artifact_type, symbol, theme, tags, ingest)


def demo(repo_root: str | Path | None = None, ingest: bool | None = True) -> list[ArtifactResult]:
    root = globals()["repo_root"](repo_root)
    return [
        save_json(module="artifact_writer_demo", artifact_type="json_result", payload={"symbol":"AMD","score":1.23,"research_only":True}, symbol="AMD", tags=["demo"], repo_root=root, ingest=ingest),
        save_csv(module="artifact_writer_demo", artifact_type="csv_result", rows=[{"symbol":"AMD","value":1},{"symbol":"NVDA","value":2}], tags=["demo"], repo_root=root, ingest=ingest),
        save_markdown(module="artifact_writer_demo", artifact_type="markdown_note", markdown="# Artifact Writer Demo\n\nResearch only.", tags=["demo"], repo_root=root, ingest=ingest),
    ]


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Central artifact writer demo.")
    p.add_argument("--repo-root", type=Path, default=None)
    p.add_argument("--demo", action="store_true")
    p.add_argument("--no-ingest", action="store_true")
    a = p.parse_args()
    if not a.demo:
        p.print_help()
        return 0
    for r in demo(a.repo_root, ingest=not a.no_ingest):
        print(dumps(r.to_dict(), sort_keys=True))
    print("Research/simulation only. No broker calls, order placement, file moves, or file deletes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
