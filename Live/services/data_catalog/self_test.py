from __future__ import annotations

from pathlib import Path
import ast
import json
import sys
import tempfile


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    repo_root = _repo_root()
    live_root = repo_root / "Live"
    pkg = live_root / "services" / "data_catalog"
    for name in ["__init__.py", "models.py", "storage.py", "artifact_registry.py", "markdown_index.py", "scanner.py"]:
        path = pkg / name
        if not path.exists():
            print(f"Missing {path}")
            return 2
        ast.parse(path.read_text(encoding="utf-8", errors="replace"))

    if str(live_root) not in sys.path:
        sys.path.insert(0, str(live_root))

    from services.data_catalog.scanner import scan_data_folder
    from services.data_catalog.storage import DataCatalogStore, default_data_catalog_paths

    with tempfile.TemporaryDirectory(prefix="data_catalog_test_", ignore_cleanup_errors=True) as tmp:
        fake_live = Path(tmp) / "Live"
        _write(fake_live / "data" / "reports" / "note.md", "# Research Note\n\n## Findings\nAMD NVDA")
        _write(fake_live / "data" / "exports" / "packet.json", json.dumps({"symbols": ["AMD", "NVDA"]}))
        _write(fake_live / "data" / "exports" / "backtest.csv", "symbol,return\nAMD,0.12\nNVDA,0.18\n")
        store = DataCatalogStore(default_data_catalog_paths(fake_live)["db_path"])
        result = scan_data_folder(fake_live, store=store)
        counts = store.counts()
        if result["status"] not in {"PASS", "PASS_WITH_ERRORS"}:
            print(result)
            return 3
        if counts["data_artifacts"] < 3 or counts["markdown_documents"] < 1 or counts["artifact_json_payloads"] < 1 or counts["artifact_csv_datasets"] < 1:
            print(counts)
            return 4

    real_store = DataCatalogStore(default_data_catalog_paths(live_root)["db_path"])
    real_result = scan_data_folder(live_root, store=real_store)
    print("v23.3 Data Catalog self-test: PASS")
    print(f"real_scan_status: {real_result['status']}")
    print(f"real_files_seen: {real_result['files_seen']}")
    print(f"real_files_indexed: {real_result['files_indexed']}")
    print(f"real_files_skipped: {real_result['files_skipped']}")
    print(f"real_artifact_type_counts: {real_result['artifact_type_counts']}")
    print(f"real_catalog_counts: {real_store.counts()}")
    print("No files were moved or deleted.")
    print("Research/simulation only. No broker calls or trade execution were made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
