from __future__ import annotations

from pathlib import Path
import json
import sys


def _bootstrap_import_path() -> Path:
    here = Path(__file__).resolve()
    live_root = here.parents[3]
    repo_root = here.parents[4]
    for path in (str(live_root), str(repo_root)):
        if path not in sys.path:
            sys.path.insert(0, path)
    return live_root


def main() -> int:
    live_root = _bootstrap_import_path()

    from services.ai.auto_lab_orchestrator.ui_report_loader import (
        load_latest_universe_report,
        load_latest_walk_forward_report,
        summarize_paths,
    )

    universe_dir = live_root / "data" / "auto_lab_universe_runs" / "_ui_self_test_universe"
    universe_dir.mkdir(parents=True, exist_ok=True)
    (universe_dir / "universe_report.md").write_text("# UI Self Test Universe\n\nok\n", encoding="utf-8")
    (universe_dir / "symbol_leaderboard.md").write_text("# Symbol Leaderboard\n\nok\n", encoding="utf-8")
    (universe_dir / "strategy_robustness_report.md").write_text("# Robustness\n\nok\n", encoding="utf-8")
    (universe_dir / "top_universe_strategy_algorithm.md").write_text("# Top\n\nok\n", encoding="utf-8")
    (universe_dir / "universe_results.json").write_text(json.dumps({"ok": True}), encoding="utf-8")

    wf_dir = live_root / "data" / "auto_lab_walk_forward_runs" / "_ui_self_test_walk_forward"
    wf_dir.mkdir(parents=True, exist_ok=True)
    (wf_dir / "walk_forward_universe_report.md").write_text("# UI Self Test Walk Forward\n\nok\n", encoding="utf-8")
    (wf_dir / "walk_forward_symbol_leaderboard.md").write_text("# WF Leaderboard\n\nok\n", encoding="utf-8")
    (wf_dir / "overfit_warning_report.md").write_text("# Overfit\n\nok\n", encoding="utf-8")
    (wf_dir / "top_walk_forward_strategy_algorithm.md").write_text("# Top WF\n\nok\n", encoding="utf-8")
    (wf_dir / "walk_forward_universe_results.json").write_text(json.dumps({"ok": True}), encoding="utf-8")

    universe = load_latest_universe_report(live_root)
    walk_forward = load_latest_walk_forward_report(live_root)

    assert universe["status"] == "ok", "Expected universe report"
    assert walk_forward["status"] == "ok", "Expected walk-forward report"
    assert "UI Self Test Universe" in universe["report_md"], "Universe report text missing"
    assert "UI Self Test Walk Forward" in walk_forward["report_md"], "Walk-forward report text missing"
    assert summarize_paths(universe["paths"]), "Expected universe paths"
    assert summarize_paths(walk_forward["paths"]), "Expected walk-forward paths"

    # Import the launcher module and construct app only if Dash is installed.
    try:
        from services.ai.auto_lab_orchestrator.auto_lab_ui_launcher import create_app
        app = create_app()
        assert app is not None, "Expected Dash app object"
        dash_status = "PASS"
    except RuntimeError as exc:
        # Dash missing should not fail repository patching; the app tells the user how to install it.
        dash_status = f"SKIPPED_RUNTIME: {exc}"

    print("AI Auto Lab UI self-test: PASS")
    print(f"dash_app_construct: {dash_status}")
    print(f"latest_universe_run_dir: {universe['run_dir']}")
    print(f"latest_walk_forward_run_dir: {walk_forward['run_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
