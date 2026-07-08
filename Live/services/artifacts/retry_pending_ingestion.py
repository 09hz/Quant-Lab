from __future__ import annotations

import argparse
from pathlib import Path
from .artifact_writer import ingest_to_db, dumps
from .pending_ingestion import list_pending, pending_count


def retry_pending(repo_root: str | Path | None = None, limit: int | None = None) -> dict:
    rows = list_pending(repo_root, limit)
    s = {"seen": len(rows), "retried": 0, "succeeded": 0, "failed": 0, "remaining": None, "failures": []}
    for r in rows:
        s["retried"] += 1
        try:
            ingest_to_db(r, root=repo_root)
            s["succeeded"] += 1
        except Exception as e:
            s["failed"] += 1
            s["failures"].append({"artifact_id": r.artifact_id, "path": r.path, "error": f"{type(e).__name__}: {e}"})
    s["remaining"] = pending_count(repo_root)
    return s


def main() -> int:
    p = argparse.ArgumentParser(description="Retry pending artifact database ingestion.")
    p.add_argument("--repo-root", type=Path, default=None)
    p.add_argument("--limit", type=int, default=None)
    a = p.parse_args()
    s = retry_pending(a.repo_root, a.limit)
    print(dumps(s, sort_keys=True))
    print("Research/simulation only. No broker calls, order placement, file moves, or file deletes.")
    return 0 if s["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
