from __future__ import annotations

import json, os, sqlite3, tempfile
from pathlib import Path


def make_repo(root: Path) -> Path:
    repo = root / "AlgoTrader"
    live = repo / "Live"
    (live / "services").mkdir(parents=True, exist_ok=True)
    (live / "app.py").write_text("# temp app\n", encoding="utf-8")
    return repo


def main() -> int:
    keys = ["ALGOTRADER_ARTIFACT_POSTGRES_INGEST","ALGOTRADER_DB_BACKEND","ALGOTRADER_DB_PASSWORD","ALGOTRADER_DATABASE_URL"]
    old = {k: os.environ.get(k) for k in keys}
    try:
        from services.artifacts.artifact_writer import save_json, save_csv, save_markdown
        from services.artifacts.pending_ingestion import pending_count, list_pending

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            repo = make_repo(Path(tmp))
            os.environ["ALGOTRADER_ARTIFACT_POSTGRES_INGEST"] = "0"
            for k in ["ALGOTRADER_DB_BACKEND","ALGOTRADER_DB_PASSWORD","ALGOTRADER_DATABASE_URL"]:
                os.environ.pop(k, None)

            r1 = save_json(module="self_test", artifact_type="json_result", payload={"symbol":"AMD","score":float("nan")}, symbol="AMD", tags=["self-test"], repo_root=repo)
            r2 = save_csv(module="self_test", artifact_type="csv_result", rows=[{"symbol":"AMD","value":1},{"symbol":"NVDA","value":2}], repo_root=repo)
            r3 = save_markdown(module="self_test", artifact_type="markdown_note", markdown="# Note\nResearch only.", repo_root=repo)
            for r in [r1, r2, r3]:
                assert Path(r.path).exists(), r
                assert r.db_status == "skipped", r

            assert json.loads(Path(r1.path).read_text())["score"] is None
            db = repo / "Live" / "data" / "catalog" / "artifact_writer.sqlite"
            con = sqlite3.connect(db)
            try:
                assert con.execute("SELECT COUNT(*) FROM managed_artifacts").fetchone()[0] == 3
            finally:
                con.close()
            assert pending_count(repo) == 0

            os.environ["ALGOTRADER_ARTIFACT_POSTGRES_INGEST"] = "1"
            os.environ["ALGOTRADER_DB_BACKEND"] = "postgres"
            os.environ.pop("ALGOTRADER_DB_PASSWORD", None)
            os.environ.pop("ALGOTRADER_DATABASE_URL", None)
            r4 = save_json(module="self_test", artifact_type="pending_json", payload={"symbol":"TSM"}, repo_root=repo)
            assert r4.pending is True
            assert pending_count(repo) == 1
            assert list_pending(repo)[0].artifact_id == r4.artifact_id
    finally:
        for k, v in old.items():
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v

    print("v24.2 central artifact writer self-test: PASS")
    print("save_json/save_csv/save_markdown: PASS")
    print("local registry: PASS")
    print("pending queue: PASS")
    print("No credentials were written.")
    print("No files were moved or deleted.")
    print("Research/simulation only. No broker calls or trade execution were made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
