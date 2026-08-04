from __future__ import annotations

from collections import deque
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid


AUTO_LAB_PROGRESS_PREFIX = "AUTOLAB_PROGRESS"


def parse_auto_lab_progress(line: str) -> dict | None:
    """Parse one machine-readable progress line emitted by an Auto Lab runner."""
    parts = str(line or "").strip().split("|", 3)
    if len(parts) != 4 or parts[0] != AUTO_LAB_PROGRESS_PREFIX:
        return None
    try:
        percent = max(0.0, min(99.5, float(parts[1])))
    except (TypeError, ValueError, OverflowError):
        return None
    return {
        "percent": round(percent, 2),
        "stage": parts[2].strip() or "running",
        "message": parts[3].strip() or "Working...",
    }


class AutoLabCommandJobManager:
    """Run bounded Auto Lab subprocesses with stable job ownership."""

    ACTIVE_STATUSES = {"queued", "running"}

    def __init__(self, *, max_output_lines: int = 2000, max_concurrent_jobs: int = 2):
        self._lock = threading.RLock()
        self._max_output_lines = max(100, int(max_output_lines or 2000))
        self._max_concurrent_jobs = max(1, int(max_concurrent_jobs or 1))
        self._jobs: dict[str, dict] = {}
        self._latest_job_id = ""

    @staticmethod
    def _idle_state() -> dict:
        return {
            "job_id": "",
            "kind": "",
            "label": "Auto Lab",
            "status": "idle",
            "percent": 0.0,
            "stage": "idle",
            "message": "Ready.",
            "started_at": "",
            "ended_at": "",
            "return_code": None,
            "error_count": 0,
            "run_dir": "",
            "command": [],
        }

    def start(
        self,
        *,
        kind: str,
        label: str,
        cmd: list[str],
        cwd: Path,
        job_id: str | None = None,
        run_dir: Path | str | None = None,
    ) -> dict:
        kind = str(kind or "").strip().lower()
        if kind not in {"universe", "walk_forward"}:
            raise ValueError(f"Unsupported Auto Lab job kind: {kind}")
        command = [str(part) for part in cmd]
        if not command:
            raise ValueError("Auto Lab command is empty.")

        with self._lock:
            active = [state for state in self._jobs.values() if state.get("status") in self.ACTIVE_STATUSES]
            same_kind = next((state for state in active if state.get("kind") == kind), None)
            if same_kind is not None:
                raise RuntimeError(
                    f"{same_kind.get('label', 'Auto Lab job')} is already running at "
                    f"{float(same_kind.get('percent') or 0.0):.0f}%."
                )
            if len(active) >= self._max_concurrent_jobs:
                raise RuntimeError(
                    f"Auto Lab job limit reached: {len(active)}/{self._max_concurrent_jobs}."
                )
            resolved_job_id = str(job_id or f"autolab_{kind}_{uuid.uuid4().hex[:12]}")
            if resolved_job_id in self._jobs:
                raise ValueError(f"Auto Lab job ID already exists: {resolved_job_id}")
            state = {
                "job_id": resolved_job_id,
                "kind": kind,
                "label": str(label or kind.replace("_", " ").title()),
                "status": "queued",
                "percent": 1.0,
                "stage": "queued",
                "message": "Queued for background execution.",
                "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "ended_at": "",
                "return_code": None,
                "error_count": 0,
                "run_dir": str(Path(run_dir).resolve()) if run_dir else "",
                "command": command,
                "_output_lines": deque(maxlen=self._max_output_lines),
                "_process": None,
            }
            self._jobs[resolved_job_id] = state
            self._latest_job_id = resolved_job_id
            queued_snapshot = self._snapshot_unlocked(state)

        worker = threading.Thread(
            target=self._run,
            args=(resolved_job_id, command, Path(cwd)),
            name=f"auto-lab-{kind}-{resolved_job_id[-8:]}",
            daemon=True,
        )
        worker.start()
        return queued_snapshot

    def snapshot(self, job_id: str | None = None, *, include_output: bool = True) -> dict:
        with self._lock:
            resolved_job_id = str(job_id or self._latest_job_id)
            state = self._jobs.get(resolved_job_id)
            return self._snapshot_unlocked(state, include_output=include_output) if state is not None else self._idle_state()

    def snapshots(self) -> list[dict]:
        with self._lock:
            return [self._snapshot_unlocked(state) for state in self._jobs.values()]

    def _snapshot_unlocked(self, state: dict, *, include_output: bool = True) -> dict:
        snapshot = {key: value for key, value in state.items() if not key.startswith("_")}
        command = list(snapshot.pop("command", []) or [])
        output_lines = list(state.get("_output_lines") or [])
        output_parts = [
            f"Started: {snapshot.get('started_at') or 'pending'}",
            f"Ended: {snapshot.get('ended_at') or 'running'}",
            f"Status: {snapshot.get('status', 'idle')}",
            f"Progress: {float(snapshot.get('percent') or 0.0):.1f}%",
        ]
        if snapshot.get("return_code") is not None:
            output_parts.append(f"Return code: {snapshot.get('return_code')}")
        output_parts.extend(
            [
                "",
                "Research/simulation only. No live orders or broker calls were made.",
                "",
                "Command:",
                " ".join(f'\"{part}\"' if " " in part else part for part in command),
                "",
                "OUTPUT:",
                *output_lines,
            ]
        )
        if include_output:
            snapshot["output"] = "\n".join(output_parts).rstrip()
        return snapshot

    def _update(self, job_id: str, **values) -> None:
        with self._lock:
            state = self._jobs.get(job_id)
            if state is not None:
                state.update(values)

    def _run(self, job_id: str, command: list[str], cwd: Path) -> None:
        self._update(
            job_id,
            status="running",
            percent=2.0,
            stage="starting",
            message="Starting the research process.",
        )
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            process = subprocess.Popen(
                command,
                cwd=str(cwd),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                creationflags=creationflags,
            )
            self._update(job_id, _process=process)
            if process.stdout is not None:
                for raw_line in process.stdout:
                    line = raw_line.rstrip("\r\n")
                    progress = parse_auto_lab_progress(line)
                    if progress is not None:
                        self._update(job_id, **progress)
                        continue
                    with self._lock:
                        state = self._jobs.get(job_id)
                        if state is not None:
                            state["_output_lines"].append(line)
                            if line.lower().startswith("errors:"):
                                try:
                                    state["error_count"] = max(0, int(line.split(":", 1)[1].strip()))
                                except (TypeError, ValueError):
                                    pass
            return_code = process.wait()
            ended_at = time.strftime("%Y-%m-%d %H:%M:%S")
            if self.snapshot(job_id, include_output=False).get("status") == "cancelled":
                self._update(job_id, return_code=return_code, _process=None)
                return
            if return_code == 0:
                error_count = int(self.snapshot(job_id).get("error_count") or 0)
                status = "completed_with_errors" if error_count else "completed"
                self._update(
                    job_id,
                    status=status,
                    percent=100.0,
                    stage=status,
                    message=(
                        f"Research reports completed with {error_count} symbol error(s)."
                        if error_count else "Research reports are ready."
                    ),
                    ended_at=ended_at,
                    return_code=return_code,
                    _process=None,
                )
            else:
                self._update(
                    job_id,
                    status="failed",
                    stage="failed",
                    message=f"Research process exited with code {return_code}.",
                    ended_at=ended_at,
                    return_code=return_code,
                    _process=None,
                )
        except Exception as exc:
            with self._lock:
                state = self._jobs.get(job_id)
                if state is not None:
                    state["_output_lines"].append(f"{exc.__class__.__name__}: {exc}")
            self._update(
                job_id,
                status="failed",
                stage="failed",
                message=f"Could not run research process: {exc}",
                ended_at=time.strftime("%Y-%m-%d %H:%M:%S"),
                return_code=-1,
                _process=None,
            )

    def cancel(self, job_id: str) -> dict:
        with self._lock:
            state = self._jobs.get(str(job_id))
            if state is None:
                raise KeyError(f"Unknown Auto Lab job ID: {job_id}")
            process = state.get("_process")
            if state.get("status") not in self.ACTIVE_STATUSES:
                return self._snapshot_unlocked(state)
            state.update(
                status="cancelled",
                stage="cancelled",
                message="Cancelled by user.",
                ended_at=time.strftime("%Y-%m-%d %H:%M:%S"),
            )
        if process is not None and process.poll() is None:
            process.terminate()
        return self.snapshot(job_id)


_AUTO_LAB_JOB_MANAGER = AutoLabCommandJobManager()


def _live_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _package_dir() -> Path:
    return Path(__file__).resolve().parent


def _clean_symbols(value: str | None) -> str:
    symbols = []
    for raw in (value or "").replace(";", ",").split(","):
        token = raw.strip().upper()
        if token and token.replace(".", "").replace("-", "").isalnum():
            symbols.append(token)
    return ",".join(dict.fromkeys(symbols)) or "AMD,NVDA,MSFT,AAPL,TSLA"


def _normalize_holdout_pct(value) -> int:
    try:
        normalized = int(float(value))
    except (TypeError, ValueError, OverflowError):
        normalized = 20
    return max(5, min(50, normalized))


def _run_command(cmd: list[str], cwd: Path) -> tuple[str, int]:
    started = time.strftime("%Y-%m-%d %H:%M:%S")
    result = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True)
    ended = time.strftime("%Y-%m-%d %H:%M:%S")
    output = "\n".join(
        [
            f"Started: {started}",
            f"Ended: {ended}",
            f"Return code: {result.returncode}",
            "",
            "Research/simulation only. No live orders or broker calls were made.",
            "",
            "Command:",
            " ".join(f'"{x}"' if " " in str(x) else str(x) for x in cmd),
            "",
            "STDOUT:",
            result.stdout or "",
            "",
            "STDERR:",
            result.stderr or "",
        ]
    )
    return output, result.returncode


def register_auto_lab_main_callbacks(app, paper_trading_service=None):
    from dash import Input, Output, State, callback_context, html, no_update
    from dash.exceptions import PreventUpdate

    from services.ai.auto_lab_orchestrator.capital_controls import (
        append_supported_capital_flags,
        money,
        normalize_capital,
    )
    from services.ai.auto_lab_orchestrator.market_memory_packet_callbacks import (
        register_market_memory_packet_callbacks,
    )
    from services.ai.auto_lab_orchestrator.script_viewer import (
        build_script_packet,
        refresh_run_manifest,
        summarize_script_paths,
        write_latest_manifest,
    )
    from services.ai.auto_lab_orchestrator.ui_report_loader import (
        load_latest_paper_review_queue,
        load_latest_universe_report,
        load_latest_walk_forward_report,
        load_paper_review_queue_from_dir,
        load_universe_report_from_dir,
        load_walk_forward_report_from_dir,
        summarize_paths,
    )
    from services.ai.auto_lab_orchestrator.walk_forward_reporter import (
        build_paper_review_overlay,
    )
    from ui.auto_lab_ui import build_auto_lab_progress_children

    live_root = _live_root()
    package_dir = _package_dir()
    python_exe = sys.executable

    def _paper_review_queue(job_store):
        jobs = _stored_jobs(job_store)
        walk_job = jobs.get("walk_forward") or {}
        job_id = str(walk_job.get("job_id") or "")
        server_snapshot = _AUTO_LAB_JOB_MANAGER.snapshot(job_id, include_output=False) if job_id else {}
        if walk_job and server_snapshot.get("job_id") != job_id:
            if not _AUTO_LAB_JOB_MANAGER.snapshots():
                return load_latest_paper_review_queue(live_root)
            walk_root = (live_root / "data" / "auto_lab_walk_forward_runs").resolve()
            return load_paper_review_queue_from_dir(walk_root / "_invalid_job_association")
        walk_run_dir = str(server_snapshot.get("run_dir") or "")
        if walk_run_dir:
            walk_root = (live_root / "data" / "auto_lab_walk_forward_runs").resolve()
            resolved_run_dir = Path(walk_run_dir).resolve()
            if resolved_run_dir.parent == walk_root:
                return load_paper_review_queue_from_dir(resolved_run_dir)
            return load_paper_review_queue_from_dir(walk_root / "_invalid_run_association")
        return load_latest_paper_review_queue(live_root)

    @app.callback(
        Output("main-autolab-capital-summary", "children"),
        Input("main-autolab-initial-cash", "value"),
        Input("main-autolab-target-cash", "value"),
        Input("main-autolab-cash-exposure", "value"),
        Input("main-autolab-sizing-mode", "value"),
        prevent_initial_call=False,
    )
    def update_capital_summary(initial_cash, target_cash, cash_exposure, sizing_mode):
        capital = normalize_capital(
            initial_cash=initial_cash,
            target_cash=target_cash,
            cash_exposure_pct=cash_exposure,
            sizing_mode=sizing_mode,
        )
        return [
            html.H4("Simulated capital assumptions"),
            html.Ul(
                [
                    html.Li(f"Starting cash: {money(capital.initial_cash)}"),
                    html.Li(f"Target cash: {money(capital.target_cash)}"),
                    html.Li(f"Target return needed: {capital.target_return_pct:.2f}%"),
                    html.Li(f"Cash exposure: {capital.cash_exposure_pct:.2f}%"),
                    html.Li(f"Sizing mode: {capital.sizing_mode}"),
                ]
            ),
            html.Strong("Research/simulation only. These are not real account balances."),
        ]

    @app.callback(
        Output("main-autolab-paper-review-candidate", "options"),
        Output("main-autolab-paper-review-candidate", "value"),
        Output("main-autolab-paper-review-preview", "children"),
        Input("main-autolab-walk-forward-report", "children"),
        Input("main-autolab-refresh", "n_clicks"),
        State("main-autolab-paper-review-candidate", "value"),
        State("main-autolab-job-store", "data"),
        prevent_initial_call=False,
    )
    def refresh_paper_review_candidates(_walk_report, _refresh_clicks, selected_review_id, job_store):
        queue = _paper_review_queue(job_store)
        candidates = list(queue.get("candidates") or [])
        options = [
            {
                "label": (
                    f"{candidate.get('symbol', '?')} | {candidate.get('candidate_id', 'candidate')} "
                    f"| Test 2 {float(candidate.get('test_score') or 0):.2f} "
                    f"| Test 4 {float(candidate.get('holdout_score') or 0):.2f}"
                ),
                "value": candidate.get("review_id"),
            }
            for candidate in candidates
            if candidate.get("review_id")
        ]
        valid_ids = {option["value"] for option in options}
        selected = selected_review_id if selected_review_id in valid_ids else (options[0]["value"] if options else None)
        candidate = next(
            (item for item in candidates if item.get("review_id") == selected),
            None,
        )
        if candidate is None:
            return options, None, "No promoted candidate is available for paper review."

        reasons = candidate.get("promotion_reasons") or []
        reason_text = "; ".join(str(reason) for reason in reasons) or "All promotion gates passed."
        preview = "\n".join(
            [
                f"Symbol: {candidate.get('symbol', '')}",
                f"Candidate: {candidate.get('candidate_id', '')}",
                f"Test 2 score: {float(candidate.get('test_score') or 0):.2f}",
                f"Test 3: {candidate.get('rolling_status', 'unknown')}",
                f"Test 4 score: {float(candidate.get('holdout_score') or 0):.2f}",
                f"Promotion evidence: {reason_text}",
                "Execution: manual paper orders only",
            ]
        )
        return options, selected, preview

    @app.callback(
        Output("main-autolab-paper-review-store", "data"),
        Output("main-autolab-paper-review-status", "children"),
        Output("watch-symbol-dropdown", "value"),
        Input("main-autolab-review-activate", "n_clicks"),
        Input("main-autolab-review-deactivate", "n_clicks"),
        State("main-autolab-paper-review-candidate", "value"),
        State("main-autolab-review-max-position", "value"),
        State("main-autolab-review-max-daily-loss", "value"),
        State("main-autolab-review-max-drawdown", "value"),
        State("main-autolab-review-max-orders", "value"),
        State("main-autolab-job-store", "data"),
        prevent_initial_call=True,
    )
    def control_paper_review(
        _activate_clicks,
        _deactivate_clicks,
        selected_review_id,
        max_position_pct,
        max_daily_loss_pct,
        max_drawdown_pct,
        max_orders_per_day,
        job_store,
    ):
        triggered = callback_context.triggered[0]["prop_id"].split(".")[0] if callback_context.triggered else ""
        if paper_trading_service is None:
            return no_update, "Paper trading service is unavailable; no review was activated.", no_update

        if triggered == "main-autolab-review-deactivate":
            status = paper_trading_service.deactivate_review()
            return status, "Paper review and its Auto Lab chart overlay were deactivated.", no_update

        if triggered != "main-autolab-review-activate":
            raise PreventUpdate
        if not selected_review_id:
            return no_update, "Select a promoted candidate before activating paper review.", no_update

        queue = _paper_review_queue(job_store)
        candidate = next(
            (
                item
                for item in queue.get("candidates", [])
                if item.get("review_id") == selected_review_id
            ),
            None,
        )
        if candidate is None:
            return no_update, "The selected promoted candidate is no longer in the latest review queue.", no_update

        try:
            overlay = build_paper_review_overlay(candidate)
            status = paper_trading_service.activate_review(
                candidate,
                risk_policy={
                    "max_position_pct": max_position_pct,
                    "max_daily_loss_pct": max_daily_loss_pct,
                    "max_drawdown_pct": max_drawdown_pct,
                    "max_orders_per_day": max_orders_per_day,
                    "allow_short": False,
                },
            )
        except Exception as exc:
            return no_update, f"Paper review activation failed: {exc}", no_update

        policy = status.get("risk_policy", {})
        return (
            {**status, "overlay": overlay},
            (
                f"Active manual review: {status.get('symbol')} / {status.get('candidate_id')} | "
                f"position {policy.get('max_position_pct', 0):g}% | "
                f"daily loss {policy.get('max_daily_loss_pct', 0):g}% | "
                f"drawdown {policy.get('max_drawdown_pct', 0):g}% | "
                f"orders/day {policy.get('max_orders_per_day', 0)}. "
                "The visual strategy overlay is loaded in Watch. No order was submitted."
            ),
            status.get("symbol"),
        )

    @app.callback(
        Output("main-autolab-symbols", "value"),
        Output("main-autolab-discovery-report", "children"),
        Output("main-autolab-discovery-paths", "children"),
        Output("main-autolab-discovery-store", "data"),
        Input("main-autolab-suggest-symbols", "n_clicks"),
        State("main-autolab-symbols", "value"),
        State("main-autolab-discovery-theme", "value"),
        State("main-autolab-discovery-max-symbols", "value"),
        State("main-autolab-discovery-store", "data"),
        prevent_initial_call=True,
    )
    def suggest_symbols(n_clicks, symbols, theme, max_symbols, discovery_state):
        if not n_clicks:
            raise PreventUpdate

        from services.ai.auto_lab_orchestrator.symbol_discovery import discover_symbol_universe
        from services.ai.auto_lab_orchestrator.symbol_discovery import normalize_symbols
        from services.ai.auto_lab_orchestrator.symbol_discovery_reporter import write_symbol_discovery_reports

        discovery_state = dict(discovery_state or {})
        current_symbols = normalize_symbols(symbols)
        last_suggested = normalize_symbols(discovery_state.get("last_suggested"))
        same_generated_input = bool(last_suggested and current_symbols == last_suggested)
        seed_symbols = (
            normalize_symbols(discovery_state.get("seed_symbols"))
            if same_generated_input
            else current_symbols
        )
        same_search = (
            seed_symbols == normalize_symbols(discovery_state.get("seed_symbols"))
            and str(theme or "").strip().lower() == str(discovery_state.get("theme") or "").strip().lower()
        )
        seen_symbols = normalize_symbols(discovery_state.get("seen_symbols")) if same_search else []
        packet = discover_symbol_universe(
            seed_symbols=seed_symbols,
            theme=theme,
            max_symbols=max_symbols or 10,
            exclude_symbols=seen_symbols,
        )
        paths = write_symbol_discovery_reports(live_root, packet)
        suggested_value = ",".join(packet.get("suggested_symbols", []))

        path_text = "\n".join(
            [
                f"run_dir: {paths.get('run_dir', '')}",
                f"report_path: {paths.get('report_path', '')}",
                f"json_path: {paths.get('json_path', '')}",
                f"manifest_path: {paths.get('manifest_path', '')}",
            ]
        )

        suggested_symbols = normalize_symbols(packet.get("suggested_symbols"))
        next_state = {
            "seed_symbols": seed_symbols,
            "seen_symbols": list(dict.fromkeys([*seen_symbols, *suggested_symbols])),
            "last_suggested": suggested_symbols,
            "theme": str(theme or ""),
        }
        return suggested_value, paths.get("report_md", ""), path_text, next_state

    def _report_packet(
        manifest_paths: dict[str, str] | None = None,
        completed_snapshot: dict | None = None,
        completed_snapshots: dict[str, dict] | None = None,
    ) -> tuple:
        completed_snapshot = dict(completed_snapshot or {})
        completed_by_kind = dict(completed_snapshots or {})
        if completed_snapshot.get("kind"):
            completed_by_kind[str(completed_snapshot["kind"])] = completed_snapshot
        universe_snapshot = dict(completed_by_kind.get("universe") or {})
        walk_snapshot = dict(completed_by_kind.get("walk_forward") or {})
        if universe_snapshot.get("run_dir"):
            universe = load_universe_report_from_dir(universe_snapshot["run_dir"])
        else:
            universe = load_latest_universe_report(live_root)
        if walk_snapshot.get("run_dir"):
            walk_forward = load_walk_forward_report_from_dir(walk_snapshot["run_dir"])
        else:
            walk_forward = load_latest_walk_forward_report(live_root)
        scripts = build_script_packet(
            live_root,
            universe_dir=(universe_snapshot.get("run_dir") or None) if not walk_snapshot.get("run_dir") else None,
            walk_dir=walk_snapshot.get("run_dir") or None,
        )
        path_text = "\n".join(
            [
                "UNIVERSE",
                summarize_paths(universe.get("paths", {})),
                "",
                "WALK_FORWARD",
                summarize_paths(walk_forward.get("paths", {})),
                "",
                "UI MANIFEST",
                summarize_paths(manifest_paths or {}),
            ]
        )
        return (
            universe.get("report_md", "No universe report available."),
            walk_forward.get("report_md", "No walk-forward report available."),
            path_text,
            scripts.get("universe_md", "No universe strategy script loaded."),
            scripts.get("walk_forward_md", "No walk-forward strategy script loaded."),
            summarize_script_paths(scripts.get("paths", {})),
        )

    def _job_store(snapshot: dict, *, consumed: bool, manifest_paths=None) -> dict:
        return {
            key: snapshot.get(key)
            for key in (
                "job_id",
                "kind",
                "label",
                "status",
                "percent",
                "stage",
                "message",
                "started_at",
                "ended_at",
                "return_code",
                "run_dir",
            )
        } | {
            "consumed": bool(consumed),
            "manifest_paths": dict(manifest_paths or {}),
        }

    def _stored_jobs(store_data: dict | None) -> dict[str, dict]:
        store_data = dict(store_data or {})
        jobs = {
            str(kind): dict(job)
            for kind, job in dict(store_data.get("jobs") or {}).items()
            if isinstance(job, dict)
        }
        legacy_kind = str(store_data.get("kind") or "")
        if legacy_kind and store_data.get("job_id") and legacy_kind not in jobs:
            jobs[legacy_kind] = store_data
        return jobs

    def _job_registry(jobs: dict[str, dict]) -> dict:
        return {"jobs": {kind: dict(job) for kind, job in jobs.items()}}

    def _active_kind_flags() -> tuple[bool, bool]:
        active_kinds = {
            str(snapshot.get("kind") or "")
            for snapshot in _AUTO_LAB_JOB_MANAGER.snapshots()
            if snapshot.get("status") in AutoLabCommandJobManager.ACTIVE_STATUSES
        }
        return "universe" in active_kinds, "walk_forward" in active_kinds

    def _progress_for_kind(kind: str, snapshot: dict | None):
        label = "Universe Auto Lab" if kind == "universe" else "Walk-Forward Validation"
        if not snapshot:
            return no_update
        return build_auto_lab_progress_children(label, snapshot)

    @app.callback(
        Output("main-autolab-command-output", "value"),
        Output("main-autolab-universe-report", "children"),
        Output("main-autolab-walk-forward-report", "children"),
        Output("main-autolab-report-paths", "children"),
        Output("main-autolab-universe-script", "children"),
        Output("main-autolab-walk-forward-script", "children"),
        Output("main-autolab-script-paths", "children"),
        Output("main-autolab-job-store", "data"),
        Output("main-autolab-universe-progress", "children"),
        Output("main-autolab-walk-forward-progress", "children"),
        Output("main-autolab-run-universe", "disabled"),
        Output("main-autolab-run-walk-forward", "disabled"),
        Input("main-autolab-run-universe", "n_clicks"),
        Input("main-autolab-run-walk-forward", "n_clicks"),
        Input("main-autolab-refresh", "n_clicks"),
        Input("ui-interval", "n_intervals"),
        State("main-autolab-job-store", "data"),
        State("main-autolab-symbols", "value"),
        State("main-autolab-sizing-mode", "value"),
        State("main-autolab-cash-exposure", "value"),
        State("main-autolab-initial-cash", "value"),
        State("main-autolab-target-cash", "value"),
        State("main-autolab-universe-start", "value"),
        State("main-autolab-universe-end", "value"),
        State("main-autolab-max-runs", "value"),
        State("main-autolab-max-mutations", "value"),
        State("main-autolab-train-start", "value"),
        State("main-autolab-train-end", "value"),
        State("main-autolab-test-start", "value"),
        State("main-autolab-test-end", "value"),
        State("main-autolab-top-n", "value"),
        State("main-autolab-holdout-pct", "value"),
        State("main-autolab-rolling-windows", "value"),
        State("main-autolab-rolling-commission", "value"),
        State("main-autolab-rolling-slippage", "value"),
        prevent_initial_call=False,
    )
    def run_or_refresh(
        _run_universe_clicks,
        _run_walk_forward_clicks,
        _refresh_clicks,
        _ui_intervals,
        current_job_store,
        symbols,
        sizing_mode,
        cash_exposure,
        initial_cash,
        target_cash,
        universe_start,
        universe_end,
        max_runs,
        max_mutations,
        train_start,
        train_end,
        test_start,
        test_end,
        top_n,
        holdout_pct,
        rolling_windows,
        rolling_commission,
        rolling_slippage,
    ):
        triggered = callback_context.triggered[0]["prop_id"].split(".")[0] if callback_context.triggered else "initial"
        current_job_store = dict(current_job_store or {})
        stored_jobs = _stored_jobs(current_job_store)

        if triggered in {"main-autolab-run-universe", "main-autolab-run-walk-forward"}:
            requested_kind = "universe" if triggered == "main-autolab-run-universe" else "walk_forward"
            active_snapshot = next(
                (
                    snapshot
                    for snapshot in _AUTO_LAB_JOB_MANAGER.snapshots()
                    if snapshot.get("kind") == requested_kind
                    and snapshot.get("status") in AutoLabCommandJobManager.ACTIVE_STATUSES
                ),
                None,
            )
            if active_snapshot is not None:
                stored_jobs[requested_kind] = _job_store(
                    active_snapshot,
                    consumed=False,
                    manifest_paths=stored_jobs.get(requested_kind, {}).get("manifest_paths"),
                )
                universe_active, walk_active = _active_kind_flags()
                return (
                    active_snapshot.get("output", "An Auto Lab research job is already running."),
                    no_update,
                    no_update,
                    no_update,
                    no_update,
                    no_update,
                    no_update,
                    _job_registry(stored_jobs),
                    _progress_for_kind("universe", active_snapshot if requested_kind == "universe" else None),
                    _progress_for_kind("walk_forward", active_snapshot if requested_kind == "walk_forward" else None),
                    universe_active,
                    walk_active,
                )

        if triggered == "ui-interval":
            if not stored_jobs:
                raise PreventUpdate
            snapshots: dict[str, dict] = {}
            completed_snapshots: dict[str, dict] = {}
            output_messages: list[str] = []
            has_active = False
            for kind, stored_job in list(stored_jobs.items()):
                job_id = str(stored_job.get("job_id") or "")
                if not job_id:
                    continue
                snapshot = _AUTO_LAB_JOB_MANAGER.snapshot(job_id, include_output=False)
                if not snapshot.get("job_id"):
                    continue
                snapshots[kind] = snapshot
                status = str(snapshot.get("status") or "")
                if status in AutoLabCommandJobManager.ACTIVE_STATUSES:
                    has_active = True
                    output_messages.append(
                        f"{snapshot.get('label', 'Auto Lab')}: {snapshot.get('message', 'running')} "
                        f"({float(snapshot.get('percent') or 0.0):.0f}%)"
                    )
                    stored_jobs[kind] = _job_store(
                        snapshot,
                        consumed=False,
                        manifest_paths=stored_job.get("manifest_paths"),
                    )
                elif status in {"completed", "completed_with_errors", "failed", "cancelled"} and not stored_job.get("consumed"):
                    full_snapshot = _AUTO_LAB_JOB_MANAGER.snapshot(job_id)
                    completed_snapshots[kind] = full_snapshot
                    output_messages.append(full_snapshot.get("output", f"{kind} finished."))
                    refreshed_manifest_paths = refresh_run_manifest(
                        live_root,
                        full_snapshot.get("run_dir") or stored_job.get("run_dir") or "",
                    )
                    stored_jobs[kind] = _job_store(
                        snapshot,
                        consumed=True,
                        manifest_paths=refreshed_manifest_paths or stored_job.get("manifest_paths"),
                    )

            if not has_active and not completed_snapshots:
                raise PreventUpdate

            manifest_paths = {
                f"{kind}_{name}": path
                for kind, stored_job in stored_jobs.items()
                for name, path in dict(stored_job.get("manifest_paths") or {}).items()
            }
            report_packet = (
                _report_packet(manifest_paths, completed_snapshots=completed_snapshots)
                if completed_snapshots
                else (no_update,) * 6
            )
            universe_active, walk_active = _active_kind_flags()
            return (
                "\n\n".join(output_messages),
                *report_packet,
                _job_registry(stored_jobs),
                _progress_for_kind("universe", snapshots.get("universe")),
                _progress_for_kind("walk_forward", snapshots.get("walk_forward")),
                universe_active,
                walk_active,
            )

        symbols_clean = _clean_symbols(symbols)
        capital = normalize_capital(
            initial_cash=initial_cash,
            target_cash=target_cash,
            cash_exposure_pct=cash_exposure,
            sizing_mode=sizing_mode,
        )

        max_runs = max_runs or 20
        max_mutations = max_mutations or 4
        top_n = top_n or 3
        holdout_pct = _normalize_holdout_pct(holdout_pct)
        rolling_windows = max(1, min(12, int(rolling_windows or 3)))
        rolling_commission = max(0.0, float(rolling_commission or 0.0))
        rolling_slippage = max(0.0, float(rolling_slippage or 0.0))

        job_kind = ""
        job_label = ""
        job_id = ""
        run_dir: Path | None = None
        cmd: list[str] = []
        flag_warnings: list[str] = []
        manifest_paths: dict[str, str] = {}

        if triggered == "main-autolab-run-universe":
            job_kind = "universe"
            job_label = "Universe Auto Lab"
            job_id = f"universe_ui_{uuid.uuid4().hex[:16]}"
            run_dir = live_root / "data" / "auto_lab_universe_runs" / job_id
            script_path = package_dir / "universe_runner.py"
            cmd = [
                python_exe,
                str(script_path),
                "--run-id",
                job_id,
                "--symbols",
                symbols_clean,
                "--start",
                str(universe_start or "2020-01-01"),
                "--end",
                str(universe_end or "2025-12-31"),
                "--sizing-mode",
                str(capital.sizing_mode),
                "--cash-exposure-pct",
                str(capital.cash_exposure_pct),
                "--max-total-runs-per-symbol",
                str(max_runs),
                "--max-mutations-per-parent",
                str(max_mutations),
                "--workers",
                "2",
                "--continue-on-error",
            ]
            cmd, flag_warnings = append_supported_capital_flags(cmd, script_path, capital)
            manifest_paths = write_latest_manifest(
                live_root,
                "universe",
                {
                    "symbols": symbols_clean,
                    "universe_start": universe_start,
                    "universe_end": universe_end,
                    "max_runs_per_symbol": max_runs,
                    "max_mutations_per_parent": max_mutations,
                },
                capital.to_dict(),
                command=cmd,
                warnings=flag_warnings,
                run_dir=run_dir,
            )

        elif triggered == "main-autolab-run-walk-forward":
            job_kind = "walk_forward"
            job_label = "Walk-Forward Validation"
            job_id = f"walk_forward_ui_{uuid.uuid4().hex[:16]}"
            run_dir = live_root / "data" / "auto_lab_walk_forward_runs" / job_id
            script_path = package_dir / "walk_forward_runner.py"
            cmd = [
                python_exe,
                str(script_path),
                "--run-id",
                job_id,
                "--symbols",
                symbols_clean,
                "--train-start",
                str(train_start or "2020-01-01"),
                "--train-end",
                str(train_end or "2023-12-31"),
                "--test-start",
                str(test_start or "2024-01-01"),
                "--test-end",
                str(test_end or "2025-12-31"),
                "--sizing-mode",
                str(capital.sizing_mode),
                "--cash-exposure-pct",
                str(capital.cash_exposure_pct),
                "--top-n-per-symbol",
                str(top_n),
                "--holdout-pct",
                str(holdout_pct),
                "--rolling-windows",
                str(rolling_windows),
                "--rolling-commission-per-order",
                str(rolling_commission),
                "--rolling-slippage-bps",
                str(rolling_slippage),
                "--max-total-runs-per-symbol",
                str(max_runs),
                "--max-mutations-per-parent",
                str(max_mutations),
                "--workers",
                "2",
                "--continue-on-error",
            ]
            universe_report = load_latest_universe_report(live_root)
            candidate_packet = Path(str(universe_report.get("run_dir") or "")) / "universe_results.json"
            if candidate_packet.is_file():
                cmd.extend(["--candidate-packet", str(candidate_packet)])
            else:
                flag_warnings.append(
                    "No completed Universe candidate packet was available; Walk-Forward will use seed fallback."
                )
            cmd, flag_warnings = append_supported_capital_flags(cmd, script_path, capital)
            manifest_paths = write_latest_manifest(
                live_root,
                "walk_forward",
                {
                    "symbols": symbols_clean,
                    "train_start": train_start,
                    "train_end": train_end,
                    "test_start": test_start,
                    "test_end": test_end,
                    "top_n_per_symbol": top_n,
                    "holdout_pct": holdout_pct,
                    "rolling_windows": rolling_windows,
                    "rolling_commission_per_order": rolling_commission,
                    "rolling_slippage_bps": rolling_slippage,
                    "max_runs_per_symbol": max_runs,
                    "max_mutations_per_parent": max_mutations,
                    "candidate_packet": str(candidate_packet) if candidate_packet.is_file() else "",
                },
                capital.to_dict(),
                command=cmd,
                warnings=flag_warnings,
                run_dir=run_dir,
            )

        if job_kind:
            try:
                snapshot = _AUTO_LAB_JOB_MANAGER.start(
                    kind=job_kind,
                    label=job_label,
                    cmd=cmd,
                    cwd=live_root.parent,
                    job_id=job_id,
                    run_dir=run_dir,
                )
            except RuntimeError as exc:
                snapshot = _AUTO_LAB_JOB_MANAGER.snapshot(job_id)
                snapshot["message"] = str(exc)
            stored_jobs[job_kind] = _job_store(
                snapshot,
                consumed=False,
                manifest_paths=manifest_paths,
            )
            universe_active, walk_active = _active_kind_flags()
            return (
                snapshot.get("output", f"{job_label} queued."),
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                _job_registry(stored_jobs),
                _progress_for_kind("universe", snapshot if job_kind == "universe" else None),
                _progress_for_kind("walk_forward", snapshot if job_kind == "walk_forward" else None),
                universe_active,
                walk_active,
            )

        report_packet = _report_packet()
        active_snapshots = {
            str(snapshot.get("kind") or ""): snapshot
            for snapshot in _AUTO_LAB_JOB_MANAGER.snapshots()
            if snapshot.get("status") in AutoLabCommandJobManager.ACTIVE_STATUSES
        }
        for kind, snapshot in active_snapshots.items():
            stored_jobs[kind] = _job_store(
                snapshot,
                consumed=False,
                manifest_paths=stored_jobs.get(kind, {}).get("manifest_paths"),
            )
        universe_active = "universe" in active_snapshots
        walk_active = "walk_forward" in active_snapshots
        return (
            "Reports refreshed.",
            *report_packet,
            _job_registry(stored_jobs),
            _progress_for_kind("universe", active_snapshots.get("universe"))
            if universe_active else build_auto_lab_progress_children("Universe Auto Lab"),
            _progress_for_kind("walk_forward", active_snapshots.get("walk_forward"))
            if walk_active else build_auto_lab_progress_children("Walk-Forward Validation"),
            universe_active,
            walk_active,
        )

    register_market_memory_packet_callbacks(
        app,
        symbol_input_id="main-autolab-symbols",
    )

# Legacy broad callback attachment retained for reference only.
# Callback ownership is now explicit in register_auto_lab_main_callbacks().
r'''
# --- v23.2.2.1 Market Memory Packet Callback Registration ---
try:
    from services.ai.auto_lab_orchestrator.market_memory_packet_callbacks import (
        register_market_memory_packet_callbacks as _v23_2_2_1_register_market_memory_packet_callbacks,
    )

    _V23_2_2_1_MEMORY_SYMBOL_INPUT_ID = "main-autolab-symbols"

    def _v23_2_2_1_wrap_callback_register(fn):
        if getattr(fn, "_v23_2_2_1_market_memory_callbacks_wrapped", False):
            return fn

        def _wrapped(app, *args, **kwargs):
            result = fn(app, *args, **kwargs)
            _v23_2_2_1_register_market_memory_packet_callbacks(
                app,
                symbol_input_id=_V23_2_2_1_MEMORY_SYMBOL_INPUT_ID,
            )
            return result

        _wrapped.__name__ = getattr(fn, "__name__", "wrapped_market_memory_callback_register")
        _wrapped.__doc__ = getattr(fn, "__doc__", None)
        _wrapped._v23_2_2_1_market_memory_callbacks_wrapped = True
        return _wrapped

    for _v23_2_2_1_name, _v23_2_2_1_obj in list(globals().items()):
        _v23_2_2_1_lower = str(_v23_2_2_1_name).lower()
        if (
            callable(_v23_2_2_1_obj)
            and "register" in _v23_2_2_1_lower
            and "callback" in _v23_2_2_1_lower
            and ("auto" in _v23_2_2_1_lower or "autolab" in _v23_2_2_1_lower or "lab" in _v23_2_2_1_lower)
            and _v23_2_2_1_name != "register_market_memory_packet_callbacks"
        ):
            globals()[_v23_2_2_1_name] = _v23_2_2_1_wrap_callback_register(_v23_2_2_1_obj)

except Exception as _v23_2_2_1_memory_callback_error:
    print(f"v23.2.2.1 Market Memory Packet Callback Registration failed: {_v23_2_2_1_memory_callback_error}")
# --- end v23.2.2.1 Market Memory Packet Callback Registration ---
'''

# BEGIN v24.6 direct producer wiring
try:
    from services.quant_schema.producer_runtime import wire_current_module
    wire_current_module(__name__, globals())
except Exception as _v24_6_direct_wiring_exc:
    print(f"[v24.6 direct producer wiring] disabled for {__name__}: {type(_v24_6_direct_wiring_exc).__name__}: {_v24_6_direct_wiring_exc}")
# END v24.6 direct producer wiring
