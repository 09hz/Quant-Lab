from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Literal
import threading
import traceback
import uuid


JobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    try:
        return dt.isoformat()
    except Exception:
        return str(dt)


@dataclass(frozen=True)
class ReplayRangeJobRequest:
    """
    Immutable replay range job request.

    The job manager is intentionally UI-framework agnostic. The actual data
    loader is injected as a callable so this module can be tested without Dash,
    IBKR, or a live ReplayService.
    """

    symbol: str
    timeframe: str
    start_date: str
    end_date: str
    speed: float = 1.0
    force_refresh: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReplayRangeJobSnapshot:
    """
    Serializable snapshot suitable for dcc.Store, logs, or tests.
    """

    job_id: str
    status: JobStatus
    request: ReplayRangeJobRequest
    created_at: str | None
    started_at: str | None
    finished_at: str | None
    progress_current: int
    progress_total: int
    percent: float
    message: str
    error: str | None = None
    result_summary: dict[str, Any] = field(default_factory=dict)

    @property
    def done(self) -> bool:
        return self.status in {"succeeded", "failed", "cancelled"}


class ReplayRangeJobCancelled(RuntimeError):
    """Raised inside a worker when cancellation has been requested."""


class ReplayRangeJobReporter:
    """
    Progress/cancel helper passed into the loader callable.
    """

    def __init__(self, job: "_ReplayRangeJob") -> None:
        self._job = job

    @property
    def job_id(self) -> str:
        return self._job.job_id

    def is_cancelled(self) -> bool:
        return self._job.cancel_event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled():
            raise ReplayRangeJobCancelled(f"Replay range job {self.job_id} cancelled.")

    def set_progress(
        self,
        current: int | None = None,
        total: int | None = None,
        message: str | None = None,
    ) -> None:
        self._job.set_progress(current=current, total=total, message=message)


LoaderCallable = Callable[[ReplayRangeJobRequest, ReplayRangeJobReporter], Any]


class _ReplayRangeJob:
    def __init__(
        self,
        *,
        job_id: str,
        request: ReplayRangeJobRequest,
        loader: LoaderCallable,
    ) -> None:
        self.job_id = job_id
        self.request = request
        self.loader = loader
        self.status: JobStatus = "queued"
        self.created_at = _utc_now()
        self.started_at: datetime | None = None
        self.finished_at: datetime | None = None
        self.progress_current = 0
        self.progress_total = 1
        self.message = "Queued"
        self.error: str | None = None
        self.result_summary: dict[str, Any] = {}
        self.cancel_event = threading.Event()
        self.lock = threading.RLock()
        self.thread: threading.Thread | None = None

    def set_progress(
        self,
        current: int | None = None,
        total: int | None = None,
        message: str | None = None,
    ) -> None:
        with self.lock:
            if total is not None:
                self.progress_total = max(1, int(total))
            if current is not None:
                self.progress_current = max(0, int(current))
            if self.progress_current > self.progress_total:
                self.progress_total = self.progress_current
            if message:
                self.message = str(message)

    def snapshot(self) -> ReplayRangeJobSnapshot:
        with self.lock:
            total = max(1, int(self.progress_total or 1))
            current = max(0, min(int(self.progress_current or 0), total))
            percent = round((current / total) * 100.0, 2)
            if self.status == "succeeded":
                percent = 100.0
            return ReplayRangeJobSnapshot(
                job_id=self.job_id,
                status=self.status,
                request=self.request,
                created_at=_iso(self.created_at),
                started_at=_iso(self.started_at),
                finished_at=_iso(self.finished_at),
                progress_current=current,
                progress_total=total,
                percent=percent,
                message=self.message,
                error=self.error,
                result_summary=dict(self.result_summary or {}),
            )


class ReplayRangeJobManager:
    """
    Small in-process background job manager for replay range loads.

    This is intentionally conservative:
      * one manager instance owns its jobs
      * no multiprocessing
      * no external queue/database
      * no Dash imports
      * cancellation is cooperative

    Patch 35b can safely poll snapshots from this manager in the UI.
    """

    def __init__(self, *, max_concurrent_jobs: int = 1) -> None:
        self.max_concurrent_jobs = max(1, int(max_concurrent_jobs or 1))
        self._jobs: dict[str, _ReplayRangeJob] = {}
        self._lock = threading.RLock()

    def _mark_dead_active_jobs_locked(self) -> None:
        """
        Release job slots if a worker thread died before updating status.
        """
        for job in self._jobs.values():
            if job.status not in {"queued", "running"}:
                continue

            thread = job.thread
            if thread is None or thread.is_alive():
                continue

            with job.lock:
                if job.status not in {"queued", "running"}:
                    continue
                job.status = "failed"
                job.finished_at = _utc_now()
                job.message = "Worker stopped"
                job.error = "Replay range worker stopped before completing."

    def active_jobs(self) -> list[ReplayRangeJobSnapshot]:
        with self._lock:
            self._mark_dead_active_jobs_locked()
            return [
                job.snapshot()
                for job in self._jobs.values()
                if job.status in {"queued", "running"}
            ]

    def start(
        self,
        request: ReplayRangeJobRequest,
        loader: LoaderCallable,
        *,
        job_id: str | None = None,
    ) -> ReplayRangeJobSnapshot:
        if not callable(loader):
            raise TypeError("loader must be callable")

        clean_request = ReplayRangeJobRequest(
            symbol=str(request.symbol or "").upper().strip(),
            timeframe=str(request.timeframe or "1 min").strip() or "1 min",
            start_date=str(request.start_date or "").strip(),
            end_date=str(request.end_date or request.start_date or "").strip(),
            speed=float(request.speed or 1.0),
            force_refresh=bool(request.force_refresh),
            metadata=dict(request.metadata or {}),
        )

        if not clean_request.symbol:
            raise ValueError("symbol is required")
        if not clean_request.start_date:
            raise ValueError("start_date is required")
        if not clean_request.end_date:
            raise ValueError("end_date is required")

        with self._lock:
            self._mark_dead_active_jobs_locked()
            running = [
                job
                for job in self._jobs.values()
                if job.status in {"queued", "running"}
            ]
            if len(running) >= self.max_concurrent_jobs:
                raise RuntimeError(
                    f"Replay range job limit reached: {len(running)}/{self.max_concurrent_jobs}"
                )

            safe_job_id = job_id or uuid.uuid4().hex[:16]
            if safe_job_id in self._jobs:
                raise ValueError(f"Replay range job already exists: {safe_job_id}")

            job = _ReplayRangeJob(
                job_id=safe_job_id,
                request=clean_request,
                loader=loader,
            )
            self._jobs[safe_job_id] = job

            thread = threading.Thread(
                target=self._run_job,
                args=(safe_job_id,),
                name=f"replay-range-job-{safe_job_id}",
                daemon=True,
            )
            job.thread = thread
            thread.start()

            return job.snapshot()

    def start_for_replay_service(
        self,
        *,
        replay_service: Any,
        symbol: str,
        timeframe: str,
        start_date: str,
        end_date: str,
        speed: float = 1.0,
        force_refresh: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> ReplayRangeJobSnapshot:
        """
        Convenience wrapper around replay_service.load_date_range(...).

        Cancellation cannot interrupt a blocking IBKR call immediately; it becomes
        effective when the loader checks the reporter before/after the call.
        """

        request = ReplayRangeJobRequest(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            speed=speed,
            force_refresh=force_refresh,
            metadata=metadata or {},
        )

        def _loader(req: ReplayRangeJobRequest, reporter: ReplayRangeJobReporter) -> dict[str, Any]:
            reporter.raise_if_cancelled()
            reporter.set_progress(0, 1, f"Loading {req.symbol} {req.timeframe} replay range...")
            result = replay_service.load_date_range(
                symbol=req.symbol,
                start_date=req.start_date,
                end_date=req.end_date,
                timeframe=req.timeframe,
                speed=req.speed,
                force_refresh=req.force_refresh,
            )
            reporter.raise_if_cancelled()
            rows = 0
            first = None
            last = None
            try:
                rows = int(len(result)) if result is not None else 0
                if rows and "time" in result.columns:
                    first = str(result["time"].iloc[0])
                    last = str(result["time"].iloc[-1])
            except Exception:
                rows = 0
            reporter.set_progress(1, 1, f"Loaded {rows:,} replay bars.")
            return {
                "rows": rows,
                "first": first,
                "last": last,
                "symbol": req.symbol,
                "timeframe": req.timeframe,
                "start_date": req.start_date,
                "end_date": req.end_date,
            }

        return self.start(request, _loader)

    def _run_job(self, job_id: str) -> None:
        job = self._jobs[job_id]
        reporter = ReplayRangeJobReporter(job)

        with job.lock:
            job.status = "running"
            job.started_at = _utc_now()
            job.message = "Running"

        try:
            reporter.raise_if_cancelled()
            result = job.loader(job.request, reporter)
            reporter.raise_if_cancelled()

            with job.lock:
                job.status = "succeeded"
                job.finished_at = _utc_now()
                job.message = job.message or "Complete"
                job.progress_current = max(job.progress_current, job.progress_total)
                job.result_summary = self._summarize_result(result)

        except ReplayRangeJobCancelled as exc:
            with job.lock:
                job.status = "cancelled"
                job.finished_at = _utc_now()
                job.message = "Cancelled"
                job.error = str(exc)

        except Exception as exc:
            with job.lock:
                job.status = "failed"
                job.finished_at = _utc_now()
                job.message = "Failed"
                job.error = f"{type(exc).__name__}: {exc}"
                job.result_summary = {
                    "traceback": traceback.format_exc(limit=12),
                }

    def _summarize_result(self, result: Any) -> dict[str, Any]:
        if result is None:
            return {"rows": 0}

        if isinstance(result, dict):
            return dict(result)

        summary: dict[str, Any] = {
            "type": type(result).__name__,
        }

        try:
            summary["rows"] = int(len(result))
        except Exception:
            pass

        try:
            if "time" in result.columns and len(result) > 0:
                summary["first"] = str(result["time"].iloc[0])
                summary["last"] = str(result["time"].iloc[-1])
        except Exception:
            pass

        return summary

    def get(self, job_id: str) -> ReplayRangeJobSnapshot | None:
        with self._lock:
            self._mark_dead_active_jobs_locked()
            job = self._jobs.get(str(job_id or ""))
            return job.snapshot() if job else None

    def list_jobs(self) -> list[ReplayRangeJobSnapshot]:
        with self._lock:
            self._mark_dead_active_jobs_locked()
            return [job.snapshot() for job in self._jobs.values()]

    def cancel(self, job_id: str) -> ReplayRangeJobSnapshot | None:
        with self._lock:
            self._mark_dead_active_jobs_locked()
            job = self._jobs.get(str(job_id or ""))
            if job is None:
                return None

            with job.lock:
                if job.status in {"succeeded", "failed", "cancelled"}:
                    return job.snapshot()
                job.cancel_event.set()
                job.message = "Cancellation requested"
                if job.status == "queued":
                    job.status = "cancelled"
                    job.finished_at = _utc_now()
                return job.snapshot()

    def cleanup_finished(self, *, max_age_seconds: int = 3600) -> int:
        cutoff_seconds = max(0, int(max_age_seconds or 0))
        now = _utc_now()
        removed = 0

        with self._lock:
            for job_id, job in list(self._jobs.items()):
                snap = job.snapshot()
                if not snap.done:
                    continue
                finished = job.finished_at or job.created_at
                age = (now - finished).total_seconds()
                if age >= cutoff_seconds:
                    self._jobs.pop(job_id, None)
                    removed += 1

        return removed


# Module-level manager for future Dash callbacks.
_default_manager: ReplayRangeJobManager | None = None
_default_manager_lock = threading.RLock()


def get_replay_range_job_manager() -> ReplayRangeJobManager:
    global _default_manager
    with _default_manager_lock:
        if _default_manager is None:
            _default_manager = ReplayRangeJobManager(max_concurrent_jobs=1)
        return _default_manager
