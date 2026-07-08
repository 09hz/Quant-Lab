from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
from typing import Any

from services.artifacts.artifact_writer import registry_path, repo_root, dumps
from services.quant_schema.result_capture import (
    capture_backtest_result,
    capture_auto_lab_result,
    capture_walk_forward_result,
    capture_universe_result,
    capture_strategy_result,
    capture_research_result,
)


def _read_registry(root: Path, limit: int | None = None) -> list[dict[str, Any]]:
    path = registry_path(root)
    if not path.exists():
        return []
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        sql = "SELECT * FROM managed_artifacts ORDER BY created_at DESC"
        params: tuple[Any, ...] = ()
        if limit:
            sql += " LIMIT ?"
            params = (int(limit),)
        return [dict(row) for row in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def _load_payload(row: dict[str, Any]) -> Any:
    path = Path(row.get("path") or "")
    ext = str(row.get("extension") or path.suffix.lower().lstrip(".")).lower()
    if not path.exists():
        return {"missing_path": str(path)}
    if ext == "json":
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    if ext == "csv":
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return {"csv_preview": lines[:25], "row_count_preview": max(0, len(lines) - 1)}
    if ext in {"md", "txt"}:
        text = path.read_text(encoding="utf-8", errors="replace")
        return {"text_preview": text[:5000]}
    return {"path": str(path), "extension": ext}


def _category(row: dict[str, Any]) -> str:
    module = str(row.get("module") or "").lower()
    artifact_type = str(row.get("artifact_type") or "").lower()
    text = f"{module} {artifact_type}"
    if "backtest" in text or "back_test" in text:
        return "backtest"
    if "auto_lab" in text or "autolab" in text:
        return "auto_lab"
    if "walk_forward" in text or "walk-forward" in text:
        return "walk_forward"
    if "universe" in text:
        return "universe"
    if "strategy" in text:
        return "strategy"
    return "research"


def promote_managed_artifacts(
    repo_root_arg: str | Path | None = None,
    *,
    preferred_backend: str | None = None,
    limit: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    root = repo_root(repo_root_arg)
    rows = _read_registry(root, limit=limit)
    summary = {
        "repo_root": str(root),
        "seen": len(rows),
        "promoted": 0,
        "artifact_only": 0,
        "failed": 0,
        "dry_run": dry_run,
        "results": [],
    }

    for row in rows:
        category = _category(row)
        context = {
            "module": row.get("module"),
            "artifact_type": row.get("artifact_type"),
            "symbol": row.get("symbol"),
            "theme": row.get("theme"),
            "path": row.get("path"),
            "source_artifact_id": row.get("artifact_id"),
            "experiment_name": f"promoted_{category}",
        }

        if dry_run:
            summary["results"].append({"artifact_id": row.get("artifact_id"), "category": category, "status": "dry_run"})
            continue

        try:
            payload = _load_payload(row)
            if category == "backtest":
                result = capture_backtest_result(payload, context=context, repo_root=root, preferred_backend=preferred_backend)
            elif category == "auto_lab":
                result = capture_auto_lab_result(payload, context=context, repo_root=root, preferred_backend=preferred_backend)
            elif category == "walk_forward":
                result = capture_walk_forward_result(payload, context=context, repo_root=root, preferred_backend=preferred_backend)
            elif category == "universe":
                result = capture_universe_result(payload, context=context, repo_root=root, preferred_backend=preferred_backend)
            elif category == "strategy":
                result = capture_strategy_result(payload, context=context, repo_root=root, preferred_backend=preferred_backend)
            else:
                result = capture_research_result(category="research", payload=payload, context=context, repo_root=root, preferred_backend=preferred_backend)

            if result.status == "captured":
                summary["promoted"] += 1
            elif result.status == "artifact_only":
                summary["artifact_only"] += 1
            else:
                summary["failed"] += 1

            if len(summary["results"]) < 25:
                summary["results"].append(result.to_dict())
        except Exception as exc:
            summary["failed"] += 1
            if len(summary["results"]) < 25:
                summary["results"].append({"artifact_id": row.get("artifact_id"), "status": "failed", "error": f"{type(exc).__name__}: {exc}"})

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote managed artifacts into typed quant schema.")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--backend", choices=["sqlite", "postgres"], default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    summary = promote_managed_artifacts(
        repo_root_arg=args.repo_root,
        preferred_backend=args.backend,
        limit=args.limit,
        dry_run=args.dry_run,
    )
    print(dumps(summary, sort_keys=True))
    print("Research/simulation only. No broker calls, order placement, file moves, or file deletes.")
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
