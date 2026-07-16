from __future__ import annotations

from pathlib import Path
import argparse
import json
import sys
from types import SimpleNamespace


def _bootstrap_import_path() -> Path:
    here = Path(__file__).resolve()
    live_root = here.parents[3]
    repo_root = here.parents[4]
    for path in (str(live_root), str(repo_root)):
        if path not in sys.path:
            sys.path.insert(0, path)
    return live_root


def _latest_run_dir(live_root: Path) -> Path | None:
    runs_dir = live_root / "data" / "auto_lab_runs"
    if not runs_dir.exists():
        return None
    for run_dir in sorted([p for p in runs_dir.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True):
        if (run_dir / "experiment_run.json").exists():
            return run_dir
    return None


def _to_namespace_run(payload: dict) -> SimpleNamespace:
    return SimpleNamespace(
        run_id=payload.get("run_id"),
        summary=payload.get("summary") or {},
        results=[SimpleNamespace(**item) for item in payload.get("results") or [] if isinstance(item, dict)],
        scorecards=[SimpleNamespace(**item) for item in payload.get("scorecards") or [] if isinstance(item, dict)],
        candidates=payload.get("candidates") or [],
        artifacts=payload.get("artifacts") or {},
    )


def _namespace_to_payload(run: SimpleNamespace, original: dict) -> dict:
    original = dict(original)
    original["summary"] = getattr(run, "summary", {})
    original["scorecards"] = [
        dict(getattr(scorecard, "__dict__", {}) or {})
        for scorecard in getattr(run, "scorecards", [])
    ]
    return original


def main() -> int:
    live_root = _bootstrap_import_path()

    parser = argparse.ArgumentParser(description="Normalize execution quality for an existing Auto Lab run.")
    parser.add_argument("--run-dir", default="")
    parser.add_argument("--latest", action="store_true")
    parser.add_argument("--rewrite-experiment-run", action="store_true")
    args = parser.parse_args()

    if args.run_dir:
        run_dir = Path(args.run_dir).expanduser().resolve()
    elif args.latest:
        latest = _latest_run_dir(live_root)
        if not latest:
            print("No run found.")
            return 2
        run_dir = latest
    else:
        print("Provide --run-dir or --latest.")
        return 2

    exp_path = run_dir / "experiment_run.json"
    if not exp_path.exists():
        print(f"Missing experiment_run.json: {exp_path}")
        return 2

    payload = json.loads(exp_path.read_text(encoding="utf-8", errors="replace"))

    from services.ai.auto_lab_orchestrator.execution_quality import normalize_run_execution_quality, write_execution_quality_report

    run = _to_namespace_run(payload)
    summary = normalize_run_execution_quality(run, context="existing_run")
    artifacts = write_execution_quality_report(run, run_dir, summary)

    if args.rewrite_experiment_run:
        exp_path.write_text(json.dumps(_namespace_to_payload(run, payload), indent=2), encoding="utf-8")

    print("Execution quality normalization complete.")
    print(f"run_dir: {run_dir}")
    print(f"normalized_count: {summary.get('normalized_count')}")
    for key, value in artifacts.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
