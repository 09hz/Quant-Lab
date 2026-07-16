from __future__ import annotations

from pathlib import Path
import csv
import hashlib
import json
import uuid

from .artifact_registry import classify_artifact, infer_symbol, infer_theme, source_module, tags_for
from .markdown_index import parse_markdown
from .models import dumps, utc_now_iso
from .storage import DataCatalogStore, default_data_catalog_paths


SKIP_SUFFIXES = {".pyc", ".tmp", ".lock", ".sqlite-wal", ".sqlite-shm", ".db-wal", ".db-shm"}
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rel(path: Path, live_root: Path) -> str:
    try:
        return str(path.relative_to(live_root)).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _skip(path: Path) -> bool:
    if any(part in SKIP_DIRS for part in path.parts):
        return True
    if path.name.startswith("data_catalog.sqlite"):
        return True
    return path.suffix.lower() in SKIP_SUFFIXES


def _json_preview(path: Path):
    try:
        obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        if isinstance(obj, dict):
            keys = [str(k) for k in list(obj.keys())[:100]]
            preview = {k: obj[k] for k in list(obj.keys())[:20]}
            return "object", keys, preview, ""
        if isinstance(obj, list):
            keys = [str(k) for k in obj[0].keys()] if obj and isinstance(obj[0], dict) else []
            return "array", keys[:100], obj[:20], ""
        return type(obj).__name__, [], obj, ""
    except Exception as exc:
        return "", [], {}, str(exc)


def _csv_preview(path: Path):
    try:
        with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
            reader = csv.DictReader(handle)
            headers = list(reader.fieldnames or [])
            sample = []
            count = 0
            for row in reader:
                count += 1
                if len(sample) < 25:
                    sample.append(dict(row))
        return headers, count, len(headers), sample, ""
    except Exception as exc:
        return [], 0, 0, [], str(exc)


def scan_data_folder(live_root: Path, data_root: Path | None = None, store: DataCatalogStore | None = None) -> dict:
    live_root = Path(live_root).resolve()
    data_root = Path(data_root or live_root / "data").resolve()
    store = store or DataCatalogStore(default_data_catalog_paths(live_root)["db_path"])
    result = {
        "run_id": "scan_" + uuid.uuid4().hex[:12],
        "started_at": utc_now_iso(),
        "completed_at": "",
        "status": "running",
        "root_path": str(data_root),
        "files_seen": 0,
        "files_indexed": 0,
        "files_skipped": 0,
        "errors": [],
        "artifact_type_counts": {},
    }

    if not data_root.exists():
        result["status"] = "missing_data_root"
        result["completed_at"] = utc_now_iso()
        store.record_scan(result)
        return result

    for path in data_root.rglob("*"):
        if not path.is_file():
            continue
        result["files_seen"] += 1
        if _skip(path):
            result["files_skipped"] += 1
            continue
        try:
            artifact_type = classify_artifact(path)
            if artifact_type == "catalog_internal":
                result["files_skipped"] += 1
                continue
            stat = path.stat()
            sha = _sha256(path)
            row = {
                "artifact_id": sha[:24],
                "artifact_type": artifact_type,
                "file_path": _rel(path, live_root),
                "file_name": path.name,
                "extension": path.suffix.lower().lstrip("."),
                "size_bytes": int(stat.st_size),
                "sha256": sha,
                "created_at": "",
                "modified_at": "",
                "indexed_at": utc_now_iso(),
                "source_module": source_module(path),
                "symbol": infer_symbol(path),
                "theme": infer_theme(path),
                "strategy_family": "",
                "run_id": "",
                "tags_json": dumps(tags_for(path, artifact_type)),
                "metadata_json": dumps({"absolute_path": str(path), "policy": "metadata_preview_only_no_move_no_delete"}),
            }
            store.upsert_artifact(row)
            result["files_indexed"] += 1
            result["artifact_type_counts"][artifact_type] = result["artifact_type_counts"].get(artifact_type, 0) + 1

            ext = row["extension"]
            if ext == "json":
                kind, keys, preview, err = _json_preview(path)
                store.upsert_json_preview(row["artifact_id"], kind, keys, preview, err)
            elif ext == "csv":
                headers, rows, cols, sample, err = _csv_preview(path)
                store.upsert_csv_preview(row["artifact_id"], headers, rows, cols, sample, err)
            elif ext == "md":
                store.upsert_markdown(row["artifact_id"], parse_markdown(path))

        except Exception as exc:
            result["errors"].append({"path": str(path), "error": str(exc)})

    result["status"] = "PASS" if not result["errors"] else "PASS_WITH_ERRORS"
    result["completed_at"] = utc_now_iso()
    store.record_scan(result)
    return result


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--live-root", type=Path, default=None)
    args = parser.parse_args()
    live_root = args.live_root or ((args.repo_root / "Live") if args.repo_root else Path.cwd())
    if live_root.name.lower() != "live" and (live_root / "Live").exists():
        live_root = live_root / "Live"
    result = scan_data_folder(live_root)
    print(result)
    return 0 if result["status"] in {"PASS", "PASS_WITH_ERRORS"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
