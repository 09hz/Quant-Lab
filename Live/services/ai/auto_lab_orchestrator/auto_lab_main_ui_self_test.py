from __future__ import annotations

from collections import Counter
from pathlib import Path
import ast
import sys
import time
import traceback


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _find_number_input(tree: ast.AST, component_id: str) -> list[object] | None:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if node.func.id != "_number_input" or not node.args:
            continue
        first_arg = node.args[0]
        if isinstance(first_arg, ast.Constant) and first_arg.value == component_id:
            return [arg.value if isinstance(arg, ast.Constant) else None for arg in node.args]
    return None


def _callback_arity(tree: ast.AST, function_name: str) -> tuple[int, int]:
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name != function_name:
            continue
        supplied = 0
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            for argument in decorator.args:
                if not isinstance(argument, ast.Call) or not isinstance(argument.func, ast.Name):
                    continue
                if argument.func.id in {"Input", "State"}:
                    supplied += 1
        accepted = len(node.args.posonlyargs) + len(node.args.args)
        return supplied, accepted
    raise AssertionError(f"Callback function not found: {function_name}")


def _walk_layout(component):
    yield component
    children = getattr(component, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            yield from _walk_layout(child)
    elif children is not None:
        yield from _walk_layout(children)


def main() -> int:
    repo_root = _repo_root()
    live_root = repo_root / "Live"
    required = [
        live_root / "ui" / "auto_lab_ui.py",
        live_root / "ui" / "tabs_ui.py",
        live_root / "assets" / "style.workstation.css",
        live_root / "callbacks.py",
        live_root / "services" / "ai" / "auto_lab_orchestrator" / "auto_lab_main_callbacks.py",
        live_root / "services" / "ai" / "auto_lab_orchestrator" / "universe_runner.py",
        live_root / "services" / "ai" / "auto_lab_orchestrator" / "walk_forward_runner.py",
        live_root / "services" / "ai" / "auto_lab_orchestrator" / "ui_report_loader.py",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        print("Missing required files:")
        print("\n".join(missing))
        return 2

    app_py = live_root / "app.py"
    text = app_py.read_text(encoding="utf-8", errors="replace")
    checks = {
        "build_auto_lab_tab_import": "build_auto_lab_tab" in text,
        "ai_auto_lab_tab_label": 'label="AI Auto Lab"' in text or "label=\'AI Auto Lab\'" in text,
        "auto_lab_tab_value": 'value="auto-lab"' in text or "value=\'auto-lab\'" in text,
        "callback_registration": "register_auto_lab_main_callbacks" in text,
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        print("Failed app.py checks:")
        print("\n".join(failed))
        return 3

    ui_path = live_root / "ui" / "auto_lab_ui.py"
    callback_path = live_root / "services" / "ai" / "auto_lab_orchestrator" / "auto_lab_main_callbacks.py"
    paper_callback_path = live_root / "callbacks.py"
    ui_tree = ast.parse(ui_path.read_text(encoding="utf-8", errors="replace"))
    callback_tree = ast.parse(callback_path.read_text(encoding="utf-8", errors="replace"))
    paper_callback_tree = ast.parse(paper_callback_path.read_text(encoding="utf-8", errors="replace"))

    callback_text = callback_path.read_text(
        encoding="utf-8",
        errors="replace",
    )
    capital_checks = {
        "capital_summary_output": 'Output("main-autolab-capital-summary", "children")' in callback_text,
        "initial_cash_input": 'Input("main-autolab-initial-cash", "value")' in callback_text,
        "target_cash_input": 'Input("main-autolab-target-cash", "value")' in callback_text,
        "cash_exposure_input": 'Input("main-autolab-cash-exposure", "value")' in callback_text,
        "sizing_mode_input": 'Input("main-autolab-sizing-mode", "value")' in callback_text,
        "rolling_windows_state": 'State("main-autolab-rolling-windows", "value")' in callback_text,
        "rolling_commission_state": 'State("main-autolab-rolling-commission", "value")' in callback_text,
        "rolling_slippage_state": 'State("main-autolab-rolling-slippage", "value")' in callback_text,
        "holdout_state": 'State("main-autolab-holdout-pct", "value")' in callback_text,
        "holdout_cli_flag": '"--holdout-pct"' in callback_text,
        "holdout_manifest_setting": '"holdout_pct": holdout_pct' in callback_text,
        "paper_review_loader": "load_latest_paper_review_queue" in callback_text,
        "paper_review_activation": "paper_trading_service.activate_review" in callback_text,
        "paper_review_deactivation": "paper_trading_service.deactivate_review" in callback_text,
        "paper_review_overlay_builder": "build_paper_review_overlay" in callback_text,
        "paper_review_selects_watch_symbol": 'Output("watch-symbol-dropdown", "value")' in callback_text,
        "paper_review_attaches_overlay": '"overlay": overlay' in callback_text,
        "manual_only_review": "No order was submitted." in callback_text,
        "paper_service_injected": "paper_trading_service=paper_trading_service" in text,
        "paper_guard_status_layout": "paper-active-review-status" in (
            live_root / "ui" / "tabs_ui.py"
        ).read_text(encoding="utf-8", errors="replace"),
        "paper_guard_status_callback": 'Output("paper-active-review-status", "children")' in (
            paper_callback_path.read_text(encoding="utf-8", errors="replace")
        ),
        "review_store_drives_strategy": 'Input("main-autolab-paper-review-store", "data")' in (
            paper_callback_path.read_text(encoding="utf-8", errors="replace")
        ),
        "review_overlay_sync": "sync_review_store" in (
            paper_callback_path.read_text(encoding="utf-8", errors="replace")
        ),
        "review_overlay_symbol_scope": "script_for_symbol" in (
            paper_callback_path.read_text(encoding="utf-8", errors="replace")
        ),
        "job_interval_polling": 'Input("ui-interval", "n_intervals")' in callback_text,
        "job_store_state": 'State("main-autolab-job-store", "data")' in callback_text,
        "universe_progress_output": 'Output("main-autolab-universe-progress", "children")' in callback_text,
        "walk_forward_progress_output": 'Output("main-autolab-walk-forward-progress", "children")' in callback_text,
        "universe_button_lock": 'Output("main-autolab-run-universe", "disabled")' in callback_text,
        "walk_forward_button_lock": 'Output("main-autolab-run-walk-forward", "disabled")' in callback_text,
    }
    failed_capital = [name for name, ok in capital_checks.items() if not ok]
    if failed_capital:
        print("Failed live capital-summary checks:")
        print("\n".join(failed_capital))
        return 4

    holdout_call = _find_number_input(ui_tree, "main-autolab-holdout-pct")
    expected_holdout_call = ["main-autolab-holdout-pct", "Final untouched holdout %", 20, 5, 50, 5]
    if holdout_call != expected_holdout_call:
        print(f"Holdout control mismatch: expected {expected_holdout_call}, received {holdout_call}")
        return 5

    supplied, accepted = _callback_arity(callback_tree, "run_or_refresh")
    if supplied != accepted:
        print(f"Callback arity mismatch: Dash supplies {supplied}, callback accepts {accepted}")
        return 6

    review_refresh_supplied, review_refresh_accepted = _callback_arity(
        callback_tree,
        "refresh_paper_review_candidates",
    )
    review_control_supplied, review_control_accepted = _callback_arity(
        callback_tree,
        "control_paper_review",
    )
    if review_refresh_supplied != review_refresh_accepted:
        print(
            "Paper review refresh callback arity mismatch: "
            f"Dash supplies {review_refresh_supplied}, callback accepts {review_refresh_accepted}"
        )
        return 6
    if review_control_supplied != review_control_accepted:
        print(
            "Paper review control callback arity mismatch: "
            f"Dash supplies {review_control_supplied}, callback accepts {review_control_accepted}"
        )
        return 6
    paper_status_supplied, paper_status_accepted = _callback_arity(
        paper_callback_tree,
        "render_active_paper_review",
    )
    if paper_status_supplied != paper_status_accepted:
        print(
            "Paper review status callback arity mismatch: "
            f"Dash supplies {paper_status_supplied}, callback accepts {paper_status_accepted}"
        )
        return 6
    strategy_store_supplied, strategy_store_accepted = _callback_arity(
        paper_callback_tree,
        "update_strategy_script_store",
    )
    if strategy_store_supplied != strategy_store_accepted:
        print(
            "Strategy store callback arity mismatch: "
            f"Dash supplies {strategy_store_supplied}, callback accepts {strategy_store_accepted}"
        )
        return 6

    if str(live_root) not in sys.path:
        sys.path.insert(0, str(live_root))
    try:
        from services.ai.auto_lab_orchestrator.auto_lab_main_callbacks import (
            AutoLabCommandJobManager,
            _normalize_holdout_pct,
            parse_auto_lab_progress,
        )
        from dash._validate import validate_layout
        from ui.auto_lab_ui import build_auto_lab_progress_children, build_auto_lab_tab

        assert _normalize_holdout_pct(None) == 20
        assert _normalize_holdout_pct(1) == 5
        assert _normalize_holdout_pct(55) == 50
        assert _normalize_holdout_pct("25") == 25
        assert _normalize_holdout_pct("invalid") == 20
        assert parse_auto_lab_progress("AUTOLAB_PROGRESS|37.5|test_3|Rolling window 2/4") == {
            "percent": 37.5,
            "stage": "test_3",
            "message": "Rolling window 2/4",
        }
        assert parse_auto_lab_progress("ordinary output") is None

        manager = AutoLabCommandJobManager(max_concurrent_jobs=2)
        started = manager.start(
            kind="universe",
            label="Universe Auto Lab",
            cmd=[
                sys.executable,
                "-u",
                "-c",
                (
                    "import time; "
                    "print('AUTOLAB_PROGRESS|40|symbol|Testing AMD', flush=True); "
                    "time.sleep(0.15); print('job output', flush=True)"
                ),
            ],
            cwd=repo_root,
            run_dir=repo_root / "universe-test-run",
        )
        walk_started = manager.start(
            kind="walk_forward",
            label="Walk-Forward Validation",
            cmd=[sys.executable, "-u", "-c", "print('errors: 1', flush=True)"],
            cwd=repo_root,
            run_dir=repo_root / "walk-test-run",
        )
        assert walk_started["job_id"] != started["job_id"]
        assert len(manager.snapshots()) == 2
        assert started["status"] in {"queued", "running"}
        deadline = time.monotonic() + 10.0
        completed = manager.snapshot(started["job_id"])
        while completed["status"] in {"queued", "running"} and time.monotonic() < deadline:
            time.sleep(0.02)
            completed = manager.snapshot(started["job_id"])
        assert completed["status"] == "completed"
        assert completed["percent"] == 100.0
        assert completed["return_code"] == 0
        assert "job output" in completed["output"]
        assert "AUTOLAB_PROGRESS" not in completed["output"].split("OUTPUT:", 1)[-1]
        assert completed["run_dir"].endswith("universe-test-run")
        walk_completed = manager.snapshot(walk_started["job_id"])
        while walk_completed["status"] in {"queued", "running"} and time.monotonic() < deadline:
            time.sleep(0.02)
            walk_completed = manager.snapshot(walk_started["job_id"])
        assert walk_completed["status"] == "completed_with_errors"
        assert walk_completed["error_count"] == 1
        assert walk_completed["run_dir"].endswith("walk-test-run")

        layout = build_auto_lab_tab()
        assert layout is not None
        validate_layout(layout, layout)
        component_ids = [
            getattr(component, "id", None)
            for component in _walk_layout(layout)
            if getattr(component, "id", None)
        ]
        duplicate_ids = {
            component_id: count
            for component_id, count in Counter(component_ids).items()
            if count > 1
        }
        assert not duplicate_ids, f"Duplicate Auto Lab component IDs: {duplicate_ids}"

        for progress_label in ("Universe Auto Lab", "Walk-Forward Validation"):
            progress_children = build_auto_lab_progress_children(progress_label)
            progress_ids = [
                getattr(component, "id", None)
                for component in _walk_layout(progress_children)
                if getattr(component, "id", None)
            ]
            memory_ids = [
                component_id
                for component_id in progress_ids
                if str(component_id).startswith("main-autolab-memory-")
            ]
            assert not memory_ids, (
                f"{progress_label} progress children contain Market Memory IDs: {memory_ids}"
            )

        holdout = next(
            component
            for component in _walk_layout(layout)
            if getattr(component, "id", None) == "main-autolab-holdout-pct"
        )
        assert (holdout.value, holdout.min, holdout.max, holdout.step) == (20, 5, 50, 5)
        components = {
            getattr(component, "id", None): component
            for component in _walk_layout(layout)
            if getattr(component, "id", None)
        }
        expected_review_ids = {
            "main-autolab-paper-review-store",
            "main-autolab-paper-review-candidate",
            "main-autolab-paper-review-preview",
            "main-autolab-review-max-position",
            "main-autolab-review-max-daily-loss",
            "main-autolab-review-max-drawdown",
            "main-autolab-review-max-orders",
            "main-autolab-review-activate",
            "main-autolab-review-deactivate",
            "main-autolab-paper-review-status",
        }
        assert expected_review_ids.issubset(components)
        expected_progress_ids = {
            "main-autolab-job-store",
            "main-autolab-universe-progress",
            "main-autolab-walk-forward-progress",
        }
        assert expected_progress_ids.issubset(components)
        assert components["main-autolab-paper-review-store"].storage_type == "session"
        assert components["main-autolab-review-max-position"].value == 20
        assert components["main-autolab-review-max-daily-loss"].value == 2
        assert components["main-autolab-review-max-drawdown"].value == 10
        assert components["main-autolab-review-max-orders"].value == 10
        layout_status = "PASS"
    except Exception as exc:
        print(f"Layout/control check failed: {exc!r}")
        traceback.print_exc()
        return 7

    print("AI Auto Lab main UI self-test: PASS")
    print(f"layout_construct: {layout_status}")
    for name, ok in checks.items():
        print(f"{name}: {ok}")
    for name, ok in capital_checks.items():
        print(f"{name}: {ok}")
    print(f"run_or_refresh_arity: {supplied}/{accepted}")
    print(f"paper_review_refresh_arity: {review_refresh_supplied}/{review_refresh_accepted}")
    print(f"paper_review_control_arity: {review_control_supplied}/{review_control_accepted}")
    print(f"paper_review_status_arity: {paper_status_supplied}/{paper_status_accepted}")
    print(f"strategy_store_arity: {strategy_store_supplied}/{strategy_store_accepted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
