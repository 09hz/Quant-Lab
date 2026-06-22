from __future__ import annotations

import os
from pathlib import Path


BOM = "\ufeff"


def _clean_env_key(key: str) -> str:
    """
    Normalize .env keys.

    Windows PowerShell can create UTF-8 files with a BOM. If the first .env line
    is AI_FEATURES_ENABLED=true, the raw key may become
    "\ufeffAI_FEATURES_ENABLED" unless the BOM is stripped.
    """
    return str(key or "").strip().lstrip(BOM).strip()


def _clean_env_value(value: str) -> str:
    value = str(value or "").strip()

    if not value:
        return ""

    if (
        (value.startswith('"') and value.endswith('"'))
        or (value.startswith("'") and value.endswith("'"))
    ):
        value = value[1:-1]

    return value.strip()


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = str(line or "").strip().lstrip(BOM).strip()

    if not stripped or stripped.startswith("#"):
        return None

    if stripped.startswith("export "):
        stripped = stripped[len("export ") :].strip()

    if "=" not in stripped:
        return None

    key, value = stripped.split("=", 1)
    key = _clean_env_key(key)
    value = _clean_env_value(value)

    if not key:
        return None

    return key, value


def load_env_file(path: str | Path, *, override: bool = False) -> int:
    """
    Load simple KEY=VALUE pairs from a local .env file.

    This intentionally uses only the Python standard library so the app does not
    require python-dotenv. Existing environment variables win unless
    override=True.

    Supported forms:
        KEY=value
        KEY="value"
        KEY='value'
        export KEY=value

    Keep secrets out of Git. This loader does not print secret values.
    """
    env_path = Path(path)

    if not env_path.exists() or not env_path.is_file():
        return 0

    loaded = 0

    # utf-8-sig safely removes a UTF-8 BOM at the start of the file. The key
    # cleaner also strips BOM defensively in case the character appears in a key.
    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        parsed = _parse_env_line(raw_line)

        if parsed is None:
            continue

        key, value = parsed

        if override or key not in os.environ:
            os.environ[key] = value
            loaded += 1

    return loaded


def discover_app_env_files() -> list[Path]:
    """
    Return likely app .env files in stable order.

    The app can be launched from PowerShell, VS Code, PyCharm, or another IDE.
    This discovers paths relative to this file instead of relying only on the
    current working directory.
    """
    live_dir = Path(__file__).resolve().parents[2]
    repo_root = live_dir.parent
    cwd = Path.cwd()

    candidates = [
        repo_root / ".env",
        live_dir / ".env",
        cwd / ".env",
    ]

    seen: set[Path] = set()
    result: list[Path] = []

    for candidate in candidates:
        resolved = candidate.resolve()

        if resolved in seen:
            continue

        seen.add(resolved)

        if resolved.exists() and resolved.is_file():
            result.append(resolved)

    return result


def load_app_env(*, override: bool = False, verbose: bool = False) -> dict[str, object]:
    """
    Load local app environment files.

    Existing terminal/IDE environment variables are preserved by default unless
    override=True. App startup should normally use override=True so the local
    project .env wins over stale IDE defaults.

    Returns a small diagnostic dictionary without exposing secret values.
    """
    files = discover_app_env_files()
    total_loaded = 0

    for env_file in files:
        total_loaded += load_env_file(env_file, override=override)

    result = {
        "files": [str(path) for path in files],
        "loaded_values": total_loaded,
        "override": override,
    }

    if verbose:
        file_text = ", ".join(result["files"]) if result["files"] else "none"
        print(f"[ENV] loaded_values={total_loaded} override={override} files={file_text}")

    return result
