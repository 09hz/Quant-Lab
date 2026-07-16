from __future__ import annotations

import argparse
import json
from pathlib import Path

from .database_ingestion import ingest_catalog_to_database


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest cataloged JSON and CSV artifacts into SQLite or PostgreSQL.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--backend", choices=["sqlite", "postgres"], default=None)
    parser.add_argument("--max-json-bytes", type=int, default=5 * 1024 * 1024)
    parser.add_argument("--max-csv-rows", type=int, default=5000)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    summary = ingest_catalog_to_database(
        repo_root=args.repo_root,
        backend=args.backend,
        max_json_bytes=args.max_json_bytes,
        max_csv_rows=args.max_csv_rows,
        limit=args.limit,
    )
    print("v24.0 database ingestion complete:")
    print(json.dumps(summary.__dict__, indent=2, sort_keys=True))
    print("Research/simulation only. No broker calls, order placement, file moves, or file deletes.")
    return 0 if summary.status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
