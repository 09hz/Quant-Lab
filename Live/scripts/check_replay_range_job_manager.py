from __future__ import annotations

from pathlib import Path
import sys
import time


LIVE_DIR = Path(__file__).resolve().parents[1]
if str(LIVE_DIR) not in sys.path:
    sys.path.insert(0, str(LIVE_DIR))


from services.replay.range_job_manager import (  # noqa: E402
    ReplayRangeJobCancelled,
    ReplayRangeJobManager,
    ReplayRangeJobRequest,
)


def wait_for(manager: ReplayRangeJobManager, job_id: str, timeout: float = 5.0):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        snap = manager.get(job_id)
        last = snap
        if snap is not None and snap.done:
            return snap
        time.sleep(0.02)
    raise TimeoutError(f"job did not finish: {last}")


def main() -> int:
    manager = ReplayRangeJobManager(max_concurrent_jobs=1)

    def fake_loader(request, reporter):
        total = 5
        for i in range(total):
            reporter.raise_if_cancelled()
            reporter.set_progress(i, total, f"fake load step {i + 1}/{total}")
            time.sleep(0.01)
        reporter.set_progress(total, total, "fake load complete")
        return {
            "rows": 123,
            "symbol": request.symbol,
            "timeframe": request.timeframe,
        }

    snap = manager.start(
        ReplayRangeJobRequest(
            symbol="msft",
            timeframe="1 hour",
            start_date="2026-01-01",
            end_date="2026-01-31",
        ),
        fake_loader,
        job_id="success-test",
    )
    print(f"started={snap.job_id} status={snap.status} percent={snap.percent}")

    done = wait_for(manager, "success-test")
    print(
        "done="
        f"{done.job_id} status={done.status} percent={done.percent} "
        f"rows={done.result_summary.get('rows')}"
    )

    if done.status != "succeeded":
        raise AssertionError(done)
    if done.percent != 100.0:
        raise AssertionError(done)
    if done.result_summary.get("rows") != 123:
        raise AssertionError(done)

    def cancellable_loader(request, reporter):
        reporter.set_progress(0, 10, "starting cancellable load")
        for i in range(10):
            if reporter.is_cancelled():
                raise ReplayRangeJobCancelled("cancel test accepted")
            reporter.set_progress(i + 1, 10, f"cancel step {i + 1}/10")
            time.sleep(0.04)
        return {"rows": 999}

    cancel_snap = manager.start(
        ReplayRangeJobRequest(
            symbol="nvda",
            timeframe="1 day",
            start_date="2026-01-01",
            end_date="2026-12-31",
        ),
        cancellable_loader,
        job_id="cancel-test",
    )
    print(f"started={cancel_snap.job_id} status={cancel_snap.status}")

    time.sleep(0.08)
    manager.cancel("cancel-test")
    cancelled = wait_for(manager, "cancel-test", timeout=5.0)
    print(
        "cancelled="
        f"{cancelled.job_id} status={cancelled.status} "
        f"message={cancelled.message}"
    )

    if cancelled.status != "cancelled":
        raise AssertionError(cancelled)

    removed = manager.cleanup_finished(max_age_seconds=0)
    print(f"cleanup_removed={removed}")

    print("OK: replay range job manager starts, reports progress, succeeds, cancels, and cleans up.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
