from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Optional


DEFAULT_EXPORT_ROOT = "exports_service"

_SECRET_KEY_PATTERNS = (
    "api_key",
    "apikey",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "bearer",
    "password",
    "passwd",
    "private_key",
)

_SECRET_VALUE_PATTERNS = [
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{16,}"),
    re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)['\"]?[A-Za-z0-9._\-]{16,}['\"]?"),
    re.compile(r"(?i)(access[_-]?token\s*[:=]\s*)['\"]?[A-Za-z0-9._\-]{16,}['\"]?"),
    re.compile(r"(?i)(password\s*[:=]\s*)['\"]?[^'\"\s]{4,}['\"]?"),
    re.compile(r"sk-[A-Za-z0-9_\-]{12,}"),
]


def _utc_timestamp() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def safe_slug(value: Any, *, fallback: str = "export", max_len: int = 80) -> str:
    text = str(value or "").strip()
    if not text:
        text = fallback
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("._-")
    if not text:
        text = fallback
    return text[:max_len]


def looks_secret_key(key: Any) -> bool:
    key_text = str(key or "").lower()
    return any(pattern in key_text for pattern in _SECRET_KEY_PATTERNS)


def redact_text(value: str) -> str:
    text = str(value)
    for pattern in _SECRET_VALUE_PATTERNS:
        def repl(match: re.Match[str]) -> str:
            if match.groups():
                return f"{match.group(1)}[REDACTED]"
            return "[REDACTED]"
        text = pattern.sub(repl, text)
    return text


def sanitize_for_export(value: Any, *, max_string_chars: int = 200_000) -> Any:
    """
    Recursively sanitize values before writing them to disk or attaching to AI.

    This helper redacts obvious secret fields and secret-looking string values.
    It is defensive, not a guarantee. Do not pass secrets into export context.
    """
    if is_dataclass(value):
        value = asdict(value)

    if isinstance(value, Mapping):
        clean: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if looks_secret_key(key_text):
                clean[key_text] = "[REDACTED]"
            else:
                clean[key_text] = sanitize_for_export(item, max_string_chars=max_string_chars)
        return clean

    if isinstance(value, (list, tuple, set)):
        return [sanitize_for_export(item, max_string_chars=max_string_chars) for item in value]

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, str):
        text = redact_text(value)
        if len(text) > max_string_chars:
            return text[:max_string_chars] + "\n\n[TRUNCATED_FOR_EXPORT]"
        return text

    if value is None or isinstance(value, (bool, int, float)):
        return value

    return redact_text(str(value))


@dataclass
class ExportRecord:
    kind: str
    title: str
    path: str
    format: str
    created_at: str
    bytes_written: int
    metadata: dict[str, Any] = field(default_factory=dict)


class ExportManager:
    """
    Local export helper.

    Files are written under an ignored local folder by default:
        exports_service/

    This class is intentionally local-only. It does not upload files, browse the
    web, call broker APIs, or call LLMs.
    """

    def __init__(self, root_dir: str | Path | None = None) -> None:
        configured = root_dir or os.getenv("APP_EXPORT_ROOT") or DEFAULT_EXPORT_ROOT
        self.root_dir = Path(configured)

    def resolve_dir(self, kind: str) -> Path:
        target = self.root_dir / safe_slug(kind, fallback="misc")
        target.mkdir(parents=True, exist_ok=True)
        return target

    def write_json(
        self,
        *,
        kind: str,
        title: str,
        payload: Any,
        filename: str | None = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> ExportRecord:
        folder = self.resolve_dir(kind)
        name = filename or f"{safe_slug(title)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        if not name.lower().endswith(".json"):
            name += ".json"
        path = folder / name

        clean_payload = sanitize_for_export(payload)
        wrapper = {
            "kind": kind,
            "title": title,
            "created_at": _utc_timestamp(),
            "metadata": sanitize_for_export(metadata or {}),
            "payload": clean_payload,
        }

        text = json.dumps(wrapper, indent=2, sort_keys=True, ensure_ascii=False)
        path.write_text(text + "\n", encoding="utf-8")
        return ExportRecord(
            kind=kind,
            title=title,
            path=str(path),
            format="json",
            created_at=wrapper["created_at"],
            bytes_written=path.stat().st_size,
            metadata=wrapper["metadata"],
        )

    def write_markdown(
        self,
        *,
        kind: str,
        title: str,
        markdown: str,
        filename: str | None = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> ExportRecord:
        folder = self.resolve_dir(kind)
        name = filename or f"{safe_slug(title)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        if not name.lower().endswith(".md"):
            name += ".md"
        path = folder / name

        clean_markdown = sanitize_for_export(markdown)
        if not isinstance(clean_markdown, str):
            clean_markdown = str(clean_markdown)

        created_at = _utc_timestamp()
        header = [
            f"<!-- kind: {kind} -->",
            f"<!-- created_at: {created_at} -->",
        ]
        if metadata:
            safe_meta = sanitize_for_export(metadata)
            header.append("<!-- metadata: " + json.dumps(safe_meta, sort_keys=True) + " -->")

        path.write_text("\n".join(header) + "\n\n" + clean_markdown.strip() + "\n", encoding="utf-8")
        return ExportRecord(
            kind=kind,
            title=title,
            path=str(path),
            format="markdown",
            created_at=created_at,
            bytes_written=path.stat().st_size,
            metadata=sanitize_for_export(metadata or {}),
        )

    def build_ai_attachment_text(
        self,
        *,
        title: str,
        sections: Mapping[str, Any],
        max_chars: int = 60_000,
    ) -> str:
        """
        Build sanitized text that can be attached to an AI prompt.

        The caller should still ask the user for explicit consent before
        sending this text to an LLM.
        """
        lines: list[str] = [
            f"# AI Context Attachment: {sanitize_for_export(title)}",
            "",
            "This context was explicitly selected by the user for advisory analysis.",
            "Do not treat it as a trade instruction. Do not place orders.",
            "",
        ]

        for section_title, value in sections.items():
            clean_title = safe_slug(section_title, fallback="section").replace("_", " ").title()
            clean_value = sanitize_for_export(value)
            if not isinstance(clean_value, str):
                clean_value = json.dumps(clean_value, indent=2, sort_keys=True, ensure_ascii=False)
            lines.extend([f"## {clean_title}", "", clean_value.strip(), ""])

        text = "\n".join(lines).strip()
        if len(text) > max_chars:
            text = text[:max_chars] + "\n\n[TRUNCATED_FOR_AI_ATTACHMENT]"
        return text
