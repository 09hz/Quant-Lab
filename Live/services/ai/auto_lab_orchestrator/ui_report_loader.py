from __future__ import annotations

from pathlib import Path
from typing import Any
import json


REPORT_LIMIT_CHARS = 60000


def live_root_from_here() -> Path:
    return Path(__file__).resolve().parents[3]


def latest_dir(base_dir: str | Path, required_file: str = "") -> Path | None:
    base = Path(base_dir)
    if not base.exists():
        return None
    dirs = [
        p
        for p in base.iterdir()
        if p.is_dir()
        and not p.name.startswith("_")
        and (not required_file or (p / required_file).is_file())
    ]
    if not dirs:
        return None
    return max(
        dirs,
        key=lambda p: (p / required_file).stat().st_mtime if required_file else p.stat().st_mtime,
    )


def read_text_file(path: str | Path, limit: int = REPORT_LIMIT_CHARS) -> str:
    path = Path(path)
    if not path.exists():
        return f"Missing file: {path}"
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > limit:
        return text[:limit] + "\n\n[truncated for UI preview]\n"
    return text


def load_universe_report_from_dir(run_dir: str | Path) -> dict[str, Any]:
    run_dir = Path(run_dir)
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
        "status": "ok" if (run_dir / "universe_report.md").exists() else "missing",
        "report_md": read_text_file(paths["universe_report"]),
        "paths": paths,
    }


def load_walk_forward_report_from_dir(run_dir: str | Path) -> dict[str, Any]:
    run_dir = Path(run_dir)
    paths = {
        "walk_forward_universe_report": str(run_dir / "walk_forward_universe_report.md"),
        "walk_forward_symbol_leaderboard": str(run_dir / "walk_forward_symbol_leaderboard.md"),
        "overfit_warning_report": str(run_dir / "overfit_warning_report.md"),
        "top_walk_forward_strategy_algorithm": str(run_dir / "top_walk_forward_strategy_algorithm.md"),
        "walk_forward_universe_results": str(run_dir / "walk_forward_universe_results.json"),
        "paper_review_queue": str(run_dir / "paper_review_queue.json"),
        "paper_review_queue_report": str(run_dir / "paper_review_queue.md"),
    }
    return {
        "kind": "walk_forward",
        "run_dir": str(run_dir),
        "status": "ok" if (run_dir / "walk_forward_universe_report.md").exists() else "missing",
        "report_md": read_text_file(paths["walk_forward_universe_report"]),
        "paths": paths,
    }


def load_latest_universe_report(live_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(live_root) if live_root else live_root_from_here()
    runs_dir = root / "data" / "auto_lab_universe_runs"
    run_dir = latest_dir(runs_dir, "universe_results.json")
    if not run_dir:
        return {
            "kind": "universe",
            "run_dir": "",
            "status": "missing",
            "report_md": "No universe run found yet.",
            "paths": {},
        }

    return load_universe_report_from_dir(run_dir)


def load_latest_walk_forward_report(live_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(live_root) if live_root else live_root_from_here()
    runs_dir = root / "data" / "auto_lab_walk_forward_runs"
    run_dir = latest_dir(runs_dir, "walk_forward_universe_results.json")
    if not run_dir:
        return {
            "kind": "walk_forward",
            "run_dir": "",
            "status": "missing",
            "report_md": "No walk-forward run found yet.",
            "paths": {},
        }

    return load_walk_forward_report_from_dir(run_dir)


def load_latest_paper_review_queue(live_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(live_root) if live_root else live_root_from_here()
    run_dir = latest_dir(root / "data" / "auto_lab_walk_forward_runs", "paper_review_queue.json")
    if not run_dir:
        return {
            "schema_version": "paper_review_queue_v24_0",
            "status": "missing",
            "run_dir": "",
            "candidate_count": 0,
            "candidates": [],
            "auto_execute": False,
        }

    return load_paper_review_queue_from_dir(run_dir)


def load_paper_review_queue_from_dir(run_dir: str | Path) -> dict[str, Any]:
    run_dir = Path(run_dir)
    queue_path = run_dir / "paper_review_queue.json"
    payload = load_json_summary(queue_path)
    if not payload:
        return {
            "schema_version": "paper_review_queue_v24_0",
            "status": "missing",
            "run_dir": str(run_dir),
            "queue_path": str(queue_path),
            "candidate_count": 0,
            "candidates": [],
            "auto_execute": False,
        }

    candidates = [
        candidate
        for candidate in payload.get("candidates", [])
        if isinstance(candidate, dict)
        and str(candidate.get("promotion_decision") or "").lower() == "promote"
    ]
    return {
        **payload,
        "status": "ok",
        "run_dir": str(run_dir),
        "queue_path": str(queue_path),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "auto_execute": False,
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
