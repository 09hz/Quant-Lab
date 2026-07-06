from __future__ import annotations

from pathlib import Path
import argparse
import sys


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
        if (run_dir / "mutation_results.json").exists():
            return run_dir
    return None


def main() -> int:
    live_root = _bootstrap_import_path()

    parser = argparse.ArgumentParser(description="Write Strategy Build Trace files for an Auto Lab run.")
    parser.add_argument("--run-dir", default="")
    parser.add_argument("--latest", action="store_true")
    args = parser.parse_args()

    if args.run_dir:
        run_dir = Path(args.run_dir).expanduser().resolve()
    elif args.latest:
        latest = _latest_run_dir(live_root)
        if not latest:
            print("No latest run with mutation_results.json found.")
            return 2
        run_dir = latest
    else:
        print("Provide --run-dir or --latest.")
        return 2

    from services.ai.auto_lab_orchestrator.strategy_trace import write_strategy_build_trace_for_report_dir

    artifacts = write_strategy_build_trace_for_report_dir(run_dir)
    print("Strategy Build Trace complete.")
    print(f"run_dir: {run_dir}")
    for key, value in artifacts.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
