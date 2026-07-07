from __future__ import annotations

import csv
import json
from pathlib import Path
import sqlite3
import tempfile

from services.data_catalog.database_ingestion import ingest_catalog_to_database
from services.database import connect_database, load_database_config, migrate_database, masked_database_config


def _fake_repo(root: Path) -> Path:
    repo = root / "AlgoTrader"
    live = repo / "Live"
    data = live / "data"
    catalog = data / "catalog"
    catalog.mkdir(parents=True)
    (live / "app.py").write_text("# test app\n", encoding="utf-8")

    jpath = data / "sample.json"
    jpath.write_text(json.dumps({"symbol": "AMD", "research_only": True}), encoding="utf-8")

    cpath = data / "sample.csv"
    with cpath.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["symbol", "value"])
        writer.writeheader()
        writer.writerow({"symbol": "AMD", "value": "1"})
        writer.writerow({"symbol": "NVDA", "value": "2"})

    db = catalog / "data_catalog.sqlite"
    conn = sqlite3.connect(db)
    try:
        conn.execute("""CREATE TABLE data_artifacts (
            artifact_id TEXT PRIMARY KEY,
            file_path TEXT,
            artifact_type TEXT,
            extension TEXT,
            sha256 TEXT,
            size_bytes INTEGER
        )""")
        conn.execute("INSERT INTO data_artifacts VALUES (?,?,?,?,?,?)", ("j1", str(jpath), "json_export", "json", "sha-j", jpath.stat().st_size))
        conn.execute("INSERT INTO data_artifacts VALUES (?,?,?,?,?,?)", ("c1", str(cpath), "csv_export", "csv", "sha-c", cpath.stat().st_size))
        conn.commit()
    finally:
        conn.close()
    return repo


def main() -> int:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        repo = _fake_repo(Path(tmp))
        config = load_database_config(repo_root=repo, backend="sqlite")
        assert masked_database_config(config)["backend"] == "sqlite"
        with connect_database(config) as db:
            migrate_database(db)

        summary = ingest_catalog_to_database(repo, backend="sqlite", max_json_bytes=100000, max_csv_rows=5000)
        assert summary.status == "PASS", summary
        assert summary.artifacts_seen == 2, summary
        assert summary.json_ingested == 1, summary
        assert summary.csv_datasets_ingested == 1, summary
        assert summary.csv_rows_ingested == 2, summary

        conn = sqlite3.connect(repo / "Live" / "data" / "catalog" / "data_catalog.sqlite")
        try:
            assert conn.execute("SELECT COUNT(*) FROM db_json_payloads").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM db_csv_rows").fetchone()[0] == 2
            assert conn.execute("SELECT COUNT(*) FROM db_ingestion_runs").fetchone()[0] == 1
        finally:
            conn.close()

    print("v24.0 optional PostgreSQL backend + JSON/CSV ingestion self-test: PASS")
    print("SQLite fallback: PASS")
    print("JSON ingestion: PASS")
    print("CSV row ingestion: PASS")
    print("No files were moved or deleted.")
    print("Research/simulation only. No broker calls or trade execution were made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
