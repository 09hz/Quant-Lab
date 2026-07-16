from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import re
import sqlite3
from typing import Any

from services.artifacts.artifact_writer import register_existing_file, repo_root, registry_path, sha256_file, dumps


SUPPORTED_EXTENSIONS = {"json", "csv", "md", "txt"}
SKIP_PARTS = {
    "managed_artifacts",
    "__pycache__",
    ".pytest_cache",
    ".ipynb_checkpoints",
}
SKIP_SUFFIXES = {
    ".sqlite",
    ".sqlite3",
    ".db",
    ".db-wal",
    ".db-shm",
    ".pkl",
    ".pickle",
    ".parquet",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".zip",
}


@dataclass
class RoutedArtifact:
    path: str
    relative_path: str
    module: str
    artifact_type: str
    extension: str
    symbol: str | None
    theme: str | None
    sha256: str
    size_bytes: int
    status: str
    artifact_id: str | None = None
    db_status: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RouteSummary:
    repo_root: str
    scanned: int = 0
    candidates: int = 0
    routed: int = 0
    skipped_existing: int = 0
    skipped_unsupported: int = 0
    skipped_too_large: int = 0
    errors: int = 0
    ingest_requested: bool = True
    results: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_lower_path(path: Path) -> str:
    return str(path).replace("\\", "/").lower()


def _extract_symbol(path: Path) -> str | None:
    """Extract a likely stock/ETF ticker from a file name.

    This intentionally splits on underscores, dashes, dots, spaces, and other
    separators because Python regex word-boundaries treat underscores as word
    characters. Example: autolab_NVDA_result.json -> NVDA.
    """
    text = path.stem.upper()
    tokens = [token for token in re.split(r"[^A-Z0-9]+|_", text) if token]
    noise = {
        "JSON",
        "CSV",
        "MD",
        "TXT",
        "PASS",
        "FAIL",
        "WARN",
        "INFO",
        "DATA",
        "RUN",
        "TEST",
        "AUTO",
        "AUTOLAB",
        "LAB",
        "MARKET",
        "MEMORY",
        "REPORT",
        "PACKET",
        "BACKTEST",
        "RESULT",
        "RESULTS",
        "UNIVERSE",
        "WALK",
        "FORWARD",
        "RESEARCH",
        "AI",
        "ML",
        "ENV",
        "LIVE",
    }
    for token in tokens:
        if 1 <= len(token) <= 5 and token.isalpha() and token not in noise:
            return token
    return None

def _extract_theme(path: Path) -> str | None:
    text = path.stem.replace("_", " ").replace("-", " ")
    lowered = text.lower()
    known = [
        "ai infrastructure semiconductors",
        "semiconductors",
        "market memory",
        "newsroom",
        "walk forward",
        "universe",
        "backtest",
        "auto lab",
    ]
    for item in known:
        if item in lowered:
            return item
    return None


def classify_artifact(path: Path) -> tuple[str, str, str | None, str | None]:
    lower = _safe_lower_path(path)
    symbol = _extract_symbol(path)
    theme = _extract_theme(path)

    if "market_memory" in lower or "market-memory" in lower:
        if "research_packet" in lower or "research-packet" in lower or "packet" in lower:
            return "market_memory", "research_packet", symbol, theme
        if "memory_report" in lower or "memory_reports" in lower or "report" in lower:
            return "market_memory", "memory_report", symbol, theme
        return "market_memory", "market_memory_artifact", symbol, theme

    if "autolab" in lower or "auto_lab" in lower or "auto-lab" in lower:
        return "auto_lab", "auto_lab_result", symbol, theme or "auto lab"

    if "walk_forward" in lower or "walk-forward" in lower:
        return "walk_forward", "walk_forward_result", symbol, theme or "walk forward"

    if "universe" in lower:
        return "universe_runner", "universe_run", symbol, theme or "universe"

    if "backtest" in lower or "back_test" in lower:
        return "backtest", "backtest_result", symbol, theme or "backtest"

    if "newsroom" in lower:
        return "newsroom", "newsroom_export", symbol, theme or "newsroom"

    if "diagnostic" in lower or "diagnostics" in lower:
        return "diagnostics", "diagnostic_report", symbol, theme

    if "strategy" in lower:
        return "strategy_engine", "strategy_result", symbol, theme

    ext = path.suffix.lower().lstrip(".")
    if ext == "json":
        return "data_catalog", "json_export", symbol, theme
    if ext == "csv":
        return "data_catalog", "csv_export", symbol, theme
    if ext == "md":
        return "data_catalog", "markdown_report", symbol, theme
    return "data_catalog", "file_artifact", symbol, theme


def should_skip_path(path: Path) -> bool:
    parts = {part.lower() for part in path.parts}
    if parts.intersection(SKIP_PARTS):
        return True
    suffix = path.suffix.lower()
    if suffix in SKIP_SUFFIXES:
        return True
    if suffix.lower().lstrip(".") not in SUPPORTED_EXTENSIONS:
        return True
    return False


def _already_registered(root: Path, path: Path, sha: str | None = None) -> bool:
    db_path = registry_path(root)
    if not db_path.exists():
        return False

    try:
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute(
                "SELECT artifact_id FROM managed_artifacts WHERE path = ? OR relative_path = ? LIMIT 1",
                (str(path), _relative(root, path)),
            ).fetchone()
            if row:
                return True
            if sha:
                # Same path check is the main rule. SHA check catches exact duplicate reroutes only
                # when earlier versions stored a different absolute path spelling.
                row = conn.execute(
                    "SELECT artifact_id FROM managed_artifacts WHERE sha256 = ? AND path = ? LIMIT 1",
                    (sha, str(path)),
                ).fetchone()
                if row:
                    return True
        finally:
            conn.close()
    except Exception:
        return False

    return False


def _relative(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except Exception:
        return str(path)


def discover_output_files(
    repo_root_arg: str | Path | None = None,
    *,
    since_minutes: int | None = None,
    max_file_bytes: int = 25 * 1024 * 1024,
    limit: int | None = None,
) -> list[Path]:
    root = repo_root(repo_root_arg)
    data_dir = root / "Live" / "data"
    if not data_dir.exists():
        return []

    since_cutoff = None
    if since_minutes is not None:
        since_cutoff = datetime.now(timezone.utc) - timedelta(minutes=int(since_minutes))

    candidates: list[Path] = []
    for path in data_dir.rglob("*"):
        if not path.is_file():
            continue
        if should_skip_path(path):
            continue
        try:
            stat = path.stat()
        except Exception:
            continue
        if stat.st_size > max_file_bytes:
            continue
        if since_cutoff is not None:
            modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            if modified < since_cutoff:
                continue
        candidates.append(path)

    candidates.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    if limit:
        candidates = candidates[: int(limit)]
    return candidates


def route_existing_outputs(
    repo_root_arg: str | Path | None = None,
    *,
    ingest: bool = True,
    since_minutes: int | None = None,
    max_file_bytes: int = 25 * 1024 * 1024,
    limit: int | None = None,
    dry_run: bool = False,
) -> RouteSummary:
    root = repo_root(repo_root_arg)
    candidates = discover_output_files(
        root,
        since_minutes=since_minutes,
        max_file_bytes=max_file_bytes,
        limit=limit,
    )

    summary = RouteSummary(
        repo_root=str(root),
        candidates=len(candidates),
        ingest_requested=bool(ingest),
        results=[],
    )

    for path in candidates:
        summary.scanned += 1
        try:
            ext = path.suffix.lower().lstrip(".")
            if ext not in SUPPORTED_EXTENSIONS:
                summary.skipped_unsupported += 1
                continue

            size = path.stat().st_size
            if size > max_file_bytes:
                summary.skipped_too_large += 1
                continue

            sha = sha256_file(path)
            module, artifact_type, symbol, theme = classify_artifact(path)

            if _already_registered(root, path, sha):
                summary.skipped_existing += 1
                if len(summary.results or []) < 25:
                    summary.results.append(
                        RoutedArtifact(
                            path=str(path),
                            relative_path=_relative(root, path),
                            module=module,
                            artifact_type=artifact_type,
                            extension=ext,
                            symbol=symbol,
                            theme=theme,
                            sha256=sha,
                            size_bytes=size,
                            status="skipped_existing",
                        ).to_dict()
                    )
                continue

            if dry_run:
                summary.routed += 1
                if len(summary.results or []) < 25:
                    summary.results.append(
                        RoutedArtifact(
                            path=str(path),
                            relative_path=_relative(root, path),
                            module=module,
                            artifact_type=artifact_type,
                            extension=ext,
                            symbol=symbol,
                            theme=theme,
                            sha256=sha,
                            size_bytes=size,
                            status="dry_run",
                        ).to_dict()
                    )
                continue

            result = register_existing_file(
                path=path,
                module=module,
                artifact_type=artifact_type,
                symbol=symbol,
                theme=theme,
                tags=["v24.3_route", "managed_output_router"],
                repo_root=root,
                ingest=ingest,
            )
            summary.routed += 1
            if len(summary.results or []) < 25:
                summary.results.append(
                    RoutedArtifact(
                        path=str(path),
                        relative_path=_relative(root, path),
                        module=module,
                        artifact_type=artifact_type,
                        extension=ext,
                        symbol=symbol,
                        theme=theme,
                        sha256=sha,
                        size_bytes=size,
                        status="routed",
                        artifact_id=result.artifact_id,
                        db_status=result.db_status,
                        error=result.db_error,
                    ).to_dict()
                )
        except Exception as exc:
            summary.errors += 1
            if len(summary.results or []) < 25:
                summary.results.append(
                    {
                        "path": str(path),
                        "relative_path": _relative(root, path),
                        "status": "error",
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )

    return summary


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Route existing Live/data outputs through the central artifact writer.")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--no-ingest", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--since-minutes", type=int, default=None)
    parser.add_argument("--max-file-bytes", type=int, default=25 * 1024 * 1024)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    summary = route_existing_outputs(
        repo_root_arg=args.repo_root,
        ingest=not args.no_ingest,
        since_minutes=args.since_minutes,
        max_file_bytes=args.max_file_bytes,
        limit=args.limit,
        dry_run=args.dry_run,
    )

    print(dumps(summary.to_dict(), sort_keys=True))
    print("Research/simulation only. No broker calls, order placement, file moves, or file deletes.")
    return 0 if summary.errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
