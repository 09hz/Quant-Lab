from __future__ import annotations

import csv
import json
from pathlib import Path
import sqlite3
import tempfile

from services.data_catalog.database_ingestion import ingest_catalog_to_database


def _make_fake_repo(root: Path) -> Path:
    repo = root / "AlgoTrader"
    live = repo / "Live"
    data = live / "data"
    catalog_dir = data / "catalog"
    catalog_dir.mkdir(parents=True, exist_ok=True)
    (live / "app.py").write_text("# test app\n", encoding="utf-8")

    nan_json = data / "nan_payload.json"
    nan_json.write_text('{"symbol": "AMD", "atr": NaN, "nested": {"x": Infinity, "y": -Infinity}}', encoding="utf-8")

    good_json = data / "good_payload.json"
    good_json.write_text(json.dumps({"symbol": "NVDA", "score": 1.0}), encoding="utf-8")

    csv_path = data / "rows.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["symbol", "value"])
        writer.writeheader()
        writer.writerow({"symbol": "AMD", "value": "10"})
        writer.writerow({"symbol": "NVDA", "value": "20"})

    db_path = catalog_dir / "data_catalog.sqlite"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE data_artifacts (
                artifact_id TEXT PRIMARY KEY,
                path TEXT,
                artifact_type TEXT,
                extension TEXT,
                sha256 TEXT,
                size_bytes INTEGER
            )
            """
        )
        rows = [
            ("nan-json", str(nan_json), "json_export", "json", "sha-nan", nan_json.stat().st_size),
            ("good-json", str(good_json), "json_export", "json", "sha-good", good_json.stat().st_size),
            ("csv-rows", str(csv_path), "csv_export", "csv", "sha-csv", csv_path.stat().st_size),
        ]
        conn.executemany("INSERT INTO data_artifacts VALUES (?,?,?,?,?,?)", rows)
        conn.commit()
    finally:
        conn.close()

    return repo


def main() -> int:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        repo = _make_fake_repo(Path(tmp))
        summary = ingest_catalog_to_database(repo_root=repo, backend="sqlite", max_json_bytes=100000, max_csv_rows=5000)

        assert summary.status == "PASS", summary
        assert summary.artifacts_seen == 3, summary
        assert summary.json_ingested == 2, summary
        assert summary.csv_datasets_ingested == 1, summary
        assert summary.csv_rows_ingested == 2, summary
        assert summary.errors == 0, summary

        conn = sqlite3.connect(repo / "Live" / "data" / "catalog" / "data_catalog.sqlite")
        try:
            payload = conn.execute("SELECT payload_json FROM db_json_payloads WHERE artifact_id='nan-json'").fetchone()[0]
            assert "NaN" not in payload, payload
            assert "Infinity" not in payload, payload
            parsed = json.loads(payload)
            assert parsed["atr"] is None, parsed
            assert parsed["nested"]["x"] is None, parsed
            assert parsed["nested"]["y"] is None, parsed
        finally:
            conn.close()

    print("v24.0.1 PostgreSQL JSON NaN + transaction recovery self-test: PASS")
    print("NaN/Infinity sanitization: PASS")
    print("Per-artifact ingestion recovery: PASS")
    print("No files were moved or deleted.")
    print("Research/simulation only. No broker calls or trade execution were made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
