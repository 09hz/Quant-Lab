from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any

from .scanner import scan_data_folder
from .storage import DataCatalogStore, default_data_catalog_paths


def find_live_root(start: Path | None = None) -> Path:
    start = (start or Path(__file__)).resolve()
    for candidate in [start, *start.parents]:
        if candidate.name.lower() == "live" and (candidate / "app.py").exists():
            return candidate
        if (candidate / "Live" / "app.py").exists():
            return candidate / "Live"
    raise RuntimeError("Could not locate Live root containing app.py")


def _db_path(live_root: Path | None = None) -> Path:
    live_root = find_live_root(live_root)
    return default_data_catalog_paths(live_root)["db_path"]


def _loads(value: str | None, default: Any = None) -> Any:
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def ensure_catalog(live_root: Path | None = None) -> DataCatalogStore:
    live_root = find_live_root(live_root)
    return DataCatalogStore(_db_path(live_root))


def _row_to_artifact(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["tags"] = _loads(item.pop("tags_json", "[]"), [])
    item["metadata"] = _loads(item.pop("metadata_json", "{}"), {})
    return item


def get_catalog_filter_options(live_root: Path | None = None) -> dict[str, list[dict[str, str]]]:
    store = ensure_catalog(live_root)
    with store.session() as conn:
        types = [
            row[0]
            for row in conn.execute(
                "SELECT DISTINCT artifact_type FROM data_artifacts WHERE artifact_type != 'catalog_internal' ORDER BY artifact_type"
            ).fetchall()
            if row[0]
        ]
        exts = [
            row[0]
            for row in conn.execute(
                "SELECT DISTINCT extension FROM data_artifacts WHERE extension != '' ORDER BY extension"
            ).fetchall()
            if row[0]
        ]

    return {
        "artifact_types": [{"label": "All artifact types", "value": ""}]
        + [{"label": item.replace("_", " ").title(), "value": item} for item in types],
        "extensions": [{"label": "All extensions", "value": ""}]
        + [{"label": item.upper(), "value": item} for item in exts],
    }


def query_artifacts(
    live_root: Path | None = None,
    artifact_type: str = "",
    extension: str = "",
    search: str = "",
    limit: int = 100,
) -> list[dict[str, Any]]:
    store = ensure_catalog(live_root)
    clauses = ["artifact_type != 'catalog_internal'"]
    values: list[Any] = []

    if artifact_type:
        clauses.append("artifact_type = ?")
        values.append(str(artifact_type))

    if extension:
        clauses.append("extension = ?")
        values.append(str(extension).lower().lstrip("."))

    search = str(search or "").strip()
    if search:
        like = f"%{search}%"
        clauses.append(
            "("
            "file_name LIKE ? OR file_path LIKE ? OR artifact_type LIKE ? OR "
            "symbol LIKE ? OR theme LIKE ? OR source_module LIKE ? OR tags_json LIKE ? OR metadata_json LIKE ?"
            ")"
        )
        values.extend([like, like, like, like.upper(), like, like, like, like])

    limit = max(10, min(int(limit or 100), 500))
    values.append(limit)

    sql = f"""
        SELECT *
        FROM data_artifacts
        WHERE {' AND '.join(clauses)}
        ORDER BY modified_at DESC, indexed_at DESC, file_name ASC
        LIMIT ?
    """

    with store.session() as conn:
        rows = conn.execute(sql, values).fetchall()

    return [_row_to_artifact(row) for row in rows]


def artifact_dropdown_options(artifacts: list[dict[str, Any]]) -> list[dict[str, str]]:
    options = []
    for item in artifacts:
        label = (
            f"{item.get('artifact_type', '')} | "
            f"{item.get('file_name', '')} | "
            f"{item.get('size_bytes', 0)} bytes"
        )
        options.append({"label": label[:180], "value": item.get("artifact_id", "")})
    return options


def _markdown_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No artifacts found."
    lines = [
        "| Type | File | Ext | Size | Symbol | Theme |",
        "|---|---|---:|---:|---|---|",
    ]
    for item in rows[:50]:
        lines.append(
            f"| `{item.get('artifact_type', '')}` | `{item.get('file_name', '')}` | "
            f"`{item.get('extension', '')}` | {int(item.get('size_bytes') or 0)} | "
            f"`{item.get('symbol', '')}` | `{item.get('theme', '')}` |"
        )
    if len(rows) > 50:
        lines.append(f"| ... | {len(rows) - 50} more rows not shown in table preview |  |  |  |  |")
    return "\n".join(lines)


def format_artifact_table_markdown(artifacts: list[dict[str, Any]]) -> str:
    return _markdown_table(artifacts)


def _get_artifact_by_id(store: DataCatalogStore, artifact_id: str) -> dict[str, Any] | None:
    with store.session() as conn:
        row = conn.execute("SELECT * FROM data_artifacts WHERE artifact_id = ?", [artifact_id]).fetchone()
    return _row_to_artifact(row) if row else None


def _read_text_preview(live_root: Path, artifact: dict[str, Any], max_chars: int = 12000) -> str:
    rel = str(artifact.get("file_path") or "")
    path = (live_root / rel).resolve()
    try:
        if not path.exists():
            return "File path no longer exists on disk."
        text = path.read_text(encoding="utf-8", errors="replace")
        if len(text) > max_chars:
            text = text[:max_chars].rstrip() + "\n\n<!-- preview truncated -->"
        return text
    except Exception as exc:
        return f"Could not read text preview: {exc}"


def _format_json_preview(store: DataCatalogStore, artifact_id: str) -> str:
    with store.session() as conn:
        row = conn.execute("SELECT * FROM artifact_json_payloads WHERE artifact_id = ?", [artifact_id]).fetchone()
    if not row:
        return "No JSON preview indexed yet. Click **Rescan Live/data**."
    item = dict(row)
    keys = _loads(item.get("top_level_keys_json"), [])
    preview = _loads(item.get("preview_json"), {})
    lines = [
        "## JSON preview",
        "",
        f"- JSON kind: `{item.get('json_kind') or 'unknown'}`",
        f"- Payload status: `{item.get('payload_status')}`",
        f"- Top-level keys: `{', '.join(keys) if keys else 'none'}`",
    ]
    if item.get("error"):
        lines.append(f"- Error: `{item.get('error')}`")
    lines.extend(["", "```json", json.dumps(preview, indent=2, ensure_ascii=False, default=str)[:12000], "```"])
    return "\n".join(lines)


def _format_csv_preview(store: DataCatalogStore, artifact_id: str) -> str:
    with store.session() as conn:
        row = conn.execute("SELECT * FROM artifact_csv_datasets WHERE artifact_id = ?", [artifact_id]).fetchone()
    if not row:
        return "No CSV preview indexed yet. Click **Rescan Live/data**."
    item = dict(row)
    headers = _loads(item.get("headers_json"), [])
    sample = _loads(item.get("sample_rows_json"), [])
    lines = [
        "## CSV preview",
        "",
        f"- Rows: `{item.get('row_count')}`",
        f"- Columns: `{item.get('column_count')}`",
        f"- Headers: `{', '.join(headers) if headers else 'none'}`",
    ]
    if item.get("error"):
        lines.append(f"- Error: `{item.get('error')}`")
    if headers and sample:
        lines.extend(["", "| " + " | ".join(headers[:12]) + " |", "|" + "|".join(["---"] * min(len(headers), 12)) + "|"])
        for row in sample[:20]:
            lines.append("| " + " | ".join(str(row.get(header, ""))[:80] for header in headers[:12]) + " |")
    return "\n".join(lines)


def _format_markdown_preview(store: DataCatalogStore, artifact_id: str, live_root: Path, artifact: dict[str, Any]) -> str:
    with store.session() as conn:
        row = conn.execute("SELECT * FROM markdown_documents WHERE artifact_id = ?", [artifact_id]).fetchone()
    if row:
        item = dict(row)
        headings = _loads(item.get("headings_json"), [])
        lines = [
            f"# {item.get('title') or artifact.get('file_name')}",
            "",
            f"- Word count: `{item.get('word_count')}`",
            f"- Line count: `{item.get('line_count')}`",
            f"- Headings: `{', '.join(headings[:15]) if headings else 'none'}`",
            "",
            "---",
            "",
            item.get("preview_text") or "",
        ]
        return "\n".join(lines)
    return _read_text_preview(live_root, artifact)


def get_artifact_preview(live_root: Path | None = None, artifact_id: str = "") -> str:
    live_root = find_live_root(live_root)
    store = ensure_catalog(live_root)
    artifact = _get_artifact_by_id(store, artifact_id)
    if not artifact:
        return "No artifact selected."

    header = [
        f"# {artifact.get('file_name', '')}",
        "",
        f"- Artifact type: `{artifact.get('artifact_type', '')}`",
        f"- Extension: `{artifact.get('extension', '')}`",
        f"- Size: `{artifact.get('size_bytes', 0)} bytes`",
        f"- Path: `{artifact.get('file_path', '')}`",
        f"- Source module: `{artifact.get('source_module', '')}`",
        f"- Symbol: `{artifact.get('symbol', '')}`",
        f"- Theme: `{artifact.get('theme', '')}`",
        f"- Tags: `{', '.join(artifact.get('tags', []))}`",
        "",
        "---",
        "",
    ]

    ext = str(artifact.get("extension") or "").lower()
    if ext == "md":
        body = _format_markdown_preview(store, artifact_id, live_root, artifact)
    elif ext == "json":
        body = _format_json_preview(store, artifact_id)
    elif ext == "csv":
        body = _format_csv_preview(store, artifact_id)
    elif ext in {"txt", "log", "html"}:
        body = "```text\n" + _read_text_preview(live_root, artifact) + "\n```"
    else:
        body = (
            "Preview is not available for this file type yet.\n\n"
            "The artifact is indexed in the catalog, but the raw file remains on disk."
        )

    return "\n".join(header) + body


def refresh_or_scan_catalog(
    live_root: Path | None = None,
    do_scan: bool = False,
    artifact_type: str = "",
    extension: str = "",
    search: str = "",
    limit: int = 100,
) -> dict[str, Any]:
    live_root = find_live_root(live_root)
    store = ensure_catalog(live_root)
    scan_result = None
    if do_scan:
        scan_result = scan_data_folder(live_root, store=store)

    artifacts = query_artifacts(
        live_root=live_root,
        artifact_type=artifact_type,
        extension=extension,
        search=search,
        limit=limit,
    )
    options = artifact_dropdown_options(artifacts)
    filters = get_catalog_filter_options(live_root)
    counts = store.counts()

    return {
        "scan_result": scan_result,
        "artifacts": artifacts,
        "artifact_options": options,
        "filter_options": filters,
        "counts": counts,
        "table_markdown": format_artifact_table_markdown(artifacts),
    }
