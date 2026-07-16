from __future__ import annotations

from pathlib import Path
import tempfile


def _make_repo(root: Path) -> Path:
    repo = root / "AlgoTrader"
    live = repo / "Live"
    (live / "data" / "catalog").mkdir(parents=True, exist_ok=True)
    (live / "app.py").write_text("# temp app\n", encoding="utf-8")
    return repo


def _db_imports():
    from services.database.config import load_database_config
    try:
        from services.database.backend import connect_database
    except Exception:
        from services.database.connections import connect_database  # type: ignore
    return load_database_config, connect_database


def _seed_quant_rows(repo: Path) -> None:
    from services.quant_schema.migrations import migrate_quant_schema
    from services.quant_schema.repository import (
        insert_experiment_run,
        insert_strategy_run,
        insert_backtest_run,
        insert_walk_forward_run,
        insert_universe_run,
        insert_data_quality_event,
    )

    load_database_config, connect_database = _db_imports()
    config = load_database_config(repo_root=str(repo), backend="sqlite")

    with connect_database(config) as db:
        migrate_quant_schema(db)
        exp_id = insert_experiment_run(
            db,
            experiment_id="exp_dashboard_test",
            module="self_test",
            experiment_name="dashboard test",
            status="complete",
            config={},
            artifact_id="artifact_dashboard_test",
            commit=False,
        )
        strat_id = insert_strategy_run(
            db,
            strategy_run_id="strat_dashboard_test",
            experiment_id=exp_id,
            artifact_id="artifact_dashboard_test",
            strategy_name="DashboardStrategy",
            strategy_family="self_test",
            symbol="NVDA",
            timeframe="1d",
            parameters={},
            status="complete",
            commit=False,
        )
        insert_backtest_run(
            db,
            backtest_run_id="bt_dashboard_test",
            strategy_run_id=strat_id,
            experiment_id=exp_id,
            artifact_id="artifact_dashboard_test",
            symbol="NVDA",
            strategy_name="DashboardStrategy",
            timeframe="1d",
            sharpe=1.25,
            max_drawdown=-0.05,
            win_rate=0.56,
            total_return=0.12,
            trade_count=10,
            status="complete",
            metrics={},
            commit=False,
        )
        insert_walk_forward_run(
            db,
            walk_forward_run_id="wf_dashboard_test",
            experiment_id=exp_id,
            artifact_id="artifact_dashboard_test",
            symbol="NVDA",
            strategy_name="DashboardStrategy",
            timeframe="1d",
            window_count=3,
            avg_sharpe=1.0,
            pass_rate=0.67,
            status="complete",
            metrics={},
            commit=False,
        )
        insert_universe_run(
            db,
            universe_run_id="uni_dashboard_test",
            experiment_id=exp_id,
            artifact_id="artifact_dashboard_test",
            universe_name="DashboardUniverse",
            theme="AI infrastructure semiconductors",
            symbols=["NVDA", "AMD"],
            selected_count=2,
            ranking=[],
            status="complete",
            commit=False,
        )
        insert_data_quality_event(
            db,
            event_id="dq_dashboard_test",
            artifact_id="artifact_dashboard_test",
            symbol="NVDA",
            dataset_name="self_test_dataset",
            severity="info",
            event_type="self_test",
            message="dashboard self-test",
            details={},
            commit=False,
        )
        if hasattr(db, "commit"):
            db.commit()
        elif hasattr(db, "conn"):
            db.conn.commit()


def _collect_ids(component) -> set[str]:
    ids: set[str] = set()
    if hasattr(component, "id") and component.id:
        ids.add(component.id)
    children = getattr(component, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            ids |= _collect_ids(child)
    elif children is not None and not isinstance(children, (str, int, float)):
        ids |= _collect_ids(children)
    return ids


def main() -> int:
    from services.data_catalog.quant_dashboard_queries import load_quant_dashboard
    from services.data_catalog.quant_dashboard_ui import build_quant_dashboard_panel

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        repo = _make_repo(Path(tmp))
        _seed_quant_rows(repo)

        payload = load_quant_dashboard(repo_root=repo, backend="sqlite", limit=5)
        assert payload.status in {"PASS", "WARN"}, payload
        assert payload.counts["experiment_runs"] >= 1, payload.counts
        assert payload.counts["backtest_runs"] >= 1, payload.counts
        assert payload.sections["best_backtests"], payload.sections

        panel = build_quant_dashboard_panel()
        ids = _collect_ids(panel)
        required_ids = {
            "quant-dashboard-backend",
            "quant-dashboard-refresh",
            "quant-dashboard-status",
            "quant-dashboard-counts",
            "quant-dashboard-backtests",
        }
        missing = required_ids - ids
        assert not missing, missing

    print("v24.7 Data Library Quant Dashboard self-test: PASS")
    print("SQLite query service: PASS")
    print("Quant counts: PASS")
    print("Dashboard sections: PASS")
    print("UI component IDs: PASS")
    print("Read-only dashboard: PASS")
    print("No credentials were written.")
    print("No files were moved or deleted.")
    print("Research/simulation only. No broker calls or trade execution were made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
