from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
LIVE = ROOT / "Live"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"Missing {label}: {needle}")


def main() -> int:
    callbacks = read(LIVE / "callbacks.py")
    tabs = read(LIVE / "ui" / "tabs_ui.py")
    app_py = read(LIVE / "app.py")
    css = read(LIVE / "assets" / "zz_replay_range_jobs.css")

    if "\n@app.callback(" in callbacks:
        raise AssertionError(
            "Found a module-level @app.callback. Run git restore .\\Live\\callbacks.py "
            "and re-run the 35b4 applier."
        )

    require(app_py, 'dcc.Store(id="replay-range-job-store"', "job store in app layout")

    require(callbacks, "def load_watch_symbol_from_request", "Watch load callback")
    require(callbacks, "def poll_replay_range_job", "job polling callback")
    require(callbacks, "def _replay_job_display_percent", "job display percent helper")
    require(callbacks, "get_replay_range_job_manager", "range job manager integration")
    require(callbacks, "manager.start_for_replay_service", "background job start")
    require(callbacks, "manager.cancel", "cancel integration")
    require(callbacks, "manager.cleanup_finished", "cleanup integration")
    require(callbacks, 'Output("replay-range-job-store", "data", allow_duplicate=True)', "job store output")

    require(tabs, "replay-range-progress", "progress UI component")
    require(tabs, "replay-range-cancel", "cancel UI component")

    require(css, ".replay-range-progress-box", "progress CSS")
    require(css, ".replay-range-progress-fill", "progress fill CSS")

    sys.path.insert(0, str(LIVE))
    from services.replay.range_job_manager import ReplayRangeJobManager  # noqa: E402

    manager = ReplayRangeJobManager(max_concurrent_jobs=1)
    if manager is None:
        raise AssertionError("ReplayRangeJobManager did not instantiate")

    print("OK: Watch background replay range UI callbacks are wired.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
