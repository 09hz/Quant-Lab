from __future__ import annotations

import json
from pathlib import Path
from .artifact_writer import ArtifactResult, registry, repo_root


def list_pending(repo_root_arg: str | Path | None = None, limit: int | None = None) -> list[ArtifactResult]:
    root = repo_root(repo_root_arg)
    with registry(root) as conn:
        sql = "SELECT * FROM pending_artifact_ingestion ORDER BY updated_at DESC"
        params = ()
        if limit:
            sql += " LIMIT ?"
            params = (int(limit),)
        rows = conn.execute(sql, params).fetchall()
    out = []
    for r in rows:
        try:
            tags = json.loads(r["tags_json"] or "[]")
        except Exception:
            tags = []
        out.append(ArtifactResult(
            artifact_id=r["artifact_id"], path=r["path"], relative_path=r["relative_path"], extension=r["extension"],
            module=r["module"], artifact_type=r["artifact_type"], symbol=r["symbol"], theme=r["theme"], tags=tags,
            sha256=r["sha256"], size_bytes=int(r["size_bytes"] or 0), created_at=r["created_at"],
            db_status="pending", db_error=r["last_error"], pending=True
        ))
    return out


def pending_count(repo_root_arg: str | Path | None = None) -> int:
    root = repo_root(repo_root_arg)
    with registry(root) as conn:
        return int(conn.execute("SELECT COUNT(*) FROM pending_artifact_ingestion").fetchone()[0])
