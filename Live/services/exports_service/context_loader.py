from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .export_manager import sanitize_for_export


@dataclass
class LoadedContext:
    path: str
    format: str
    title: str
    payload: Any
    text: str


def load_context_file(path: str | Path, *, max_chars: int = 200_000) -> LoadedContext:
    """
    Load a local exported JSON/Markdown/text context file.

    This does not call the network or LLM. It only reads local user-selected
    files and sanitizes obvious secrets.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Context file not found: {p}")

    suffix = p.suffix.lower()
    raw = p.read_text(encoding="utf-8", errors="replace")
    if len(raw) > max_chars:
        raw = raw[:max_chars] + "\n\n[TRUNCATED_ON_LOAD]"

    if suffix == ".json":
        data = json.loads(raw)
        payload = sanitize_for_export(data)
        title = str(payload.get("title") or p.stem) if isinstance(payload, dict) else p.stem
        text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
        fmt = "json"
    elif suffix in {".md", ".markdown"}:
        payload = sanitize_for_export(raw)
        title = p.stem
        text = str(payload)
        fmt = "markdown"
    else:
        payload = sanitize_for_export(raw)
        title = p.stem
        text = str(payload)
        fmt = "text"

    return LoadedContext(
        path=str(p),
        format=fmt,
        title=title,
        payload=payload,
        text=text,
    )


def load_context_directory(
    root: str | Path,
    *,
    extensions: tuple[str, ...] = (".json", ".md", ".markdown", ".txt"),
    max_files: int = 50,
) -> list[LoadedContext]:
    """
    Load exported context files from a local directory for review/attachment.

    Use this for explicit user-selected export folders only.
    """
    folder = Path(root)
    if not folder.exists():
        return []

    results: list[LoadedContext] = []
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in extensions:
            continue
        results.append(load_context_file(path))
        if len(results) >= max_files:
            break
    return results
