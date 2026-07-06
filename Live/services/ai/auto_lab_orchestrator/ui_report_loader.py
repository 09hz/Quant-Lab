from __future__ import annotations

from pathlib import Path
from typing import Any
import json


REPORT_LIMIT_CHARS = 60000


def live_root_from_here() -> Path:
    return Path(__file__).resolve().parents[3]


def latest_dir(base_dir: str | Path) -> Path | None:
    base = Path(base_dir)
    if not base.exists():
        return None
    dirs = [p for p in base.iterdir() if p.is_dir()]
    if not dirs:
        return None
    return sorted(dirs, key=lambda p: p.stat().st_mtime, reverse=True)[0]


def read_text_file(path: str | Path, limit: int = REPORT_LIMIT_CHARS) -> str:
    path = Path(path)
    if not path.exists():
        return f"Missing file: {path}"
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > limit:
        return text[:limit] + "\n\n[truncated for UI preview]\n"
    return text


def load_latest_universe_report(live_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(live_root) if live_root else live_root_from_here()
    runs_dir = root / "data" / "auto_lab_universe_runs"
    run_dir = latest_dir(runs_dir)
    if not run_dir:
        return {
            "kind": "universe",
            "run_dir": "",
            "status": "missing",
            "report_md": "No universe run found yet.",
            "paths": {},
        }

    paths = {
        "universe_report": str(run_dir / "universe_report.md"),
        "symbol_leaderboard": str(run_dir / "symbol_leaderboard.md"),
        "strategy_robustness_report": str(run_dir / "strategy_robustness_report.md"),
        "top_universe_strategy_algorithm": str(run_dir / "top_universe_strategy_algorithm.md"),
        "universe_results": str(run_dir / "universe_results.json"),
    }
    return {
        "kind": "universe",
        "run_dir": str(run_dir),
        "status": "ok",
        "report_md": read_text_file(paths["universe_report"]),
        "paths": paths,
    }


def load_latest_walk_forward_report(live_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(live_root) if live_root else live_root_from_here()
    runs_dir = root / "data" / "auto_lab_walk_forward_runs"
    run_dir = latest_dir(runs_dir)
    if not run_dir:
        return {
            "kind": "walk_forward",
            "run_dir": "",
            "status": "missing",
            "report_md": "No walk-forward run found yet.",
            "paths": {},
        }

    paths = {
        "walk_forward_universe_report": str(run_dir / "walk_forward_universe_report.md"),
        "walk_forward_symbol_leaderboard": str(run_dir / "walk_forward_symbol_leaderboard.md"),
        "overfit_warning_report": str(run_dir / "overfit_warning_report.md"),
        "top_walk_forward_strategy_algorithm": str(run_dir / "top_walk_forward_strategy_algorithm.md"),
        "walk_forward_universe_results": str(run_dir / "walk_forward_universe_results.json"),
    }
    return {
        "kind": "walk_forward",
        "run_dir": str(run_dir),
        "status": "ok",
        "report_md": read_text_file(paths["walk_forward_universe_report"]),
        "paths": paths,
    }


def summarize_paths(paths: dict[str, str]) -> str:
    if not paths:
        return "No report paths available."
    lines = []
    for name, path in paths.items():
        lines.append(f"{name}: {path}")
    return "\n".join(lines)


def load_json_summary(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
