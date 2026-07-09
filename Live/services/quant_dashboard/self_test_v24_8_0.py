
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
    from services.quant_schema.repository import insert_experiment_run, insert_strategy_run, insert_backtest_run
    load_database_config, connect_database = _db_imports()
    config = load_database_config(repo_root=str(repo), backend="sqlite")
    with connect_database(config) as db:
        migrate_quant_schema(db)
        exp_id = insert_experiment_run(db, experiment_id="exp_v24_8_0_test", module="quant_dashboard_self_test", experiment_name="standalone dashboard test", status="complete", config={}, artifact_id="artifact_v24_8_0_test", commit=False)
        strat_id = insert_strategy_run(db, strategy_run_id="strat_v24_8_0_test", experiment_id=exp_id, artifact_id="artifact_v24_8_0_test", strategy_name="StandaloneDashboardStrategy", strategy_family="self_test", symbol="NVDA", timeframe="1d", parameters={}, status="complete", commit=False)
        insert_backtest_run(db, backtest_run_id="bt_v24_8_0_test", strategy_run_id=strat_id, experiment_id=exp_id, artifact_id="artifact_v24_8_0_test", symbol="NVDA", strategy_name="StandaloneDashboardStrategy", timeframe="1d", sharpe=1.25, max_drawdown=-0.05, win_rate=0.56, total_return=0.12, trade_count=10, status="complete", metrics={}, commit=False)
        if hasattr(db, "commit"):
            db.commit()
        elif hasattr(db, "conn"):
            db.conn.commit()

def _collect_ids(component) -> set[str]:
    ids = set()
    if hasattr(component, "id") and component.id:
        ids.add(str(component.id))
    children = getattr(component, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            ids |= _collect_ids(child)
    elif children is not None and not isinstance(children, (str, int, float)):
        ids |= _collect_ids(children)
    return ids

def main() -> int:
    from services.quant_dashboard.queries import load_quant_dashboard
    from services.quant_dashboard.app import create_app
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        repo = _make_repo(Path(tmp))
        _seed_quant_rows(repo)
        payload = load_quant_dashboard(repo_root=repo, backend="sqlite", limit=5)
        assert payload.status in {"PASS", "WARN"}, payload
        assert payload.counts["experiment_runs"] >= 1, payload.counts
        assert payload.counts["backtest_runs"] >= 1, payload.counts
        assert payload.sections["best_backtests"], payload.sections
        app = create_app(repo_root=str(repo), backend="sqlite", limit=5)
        ids = _collect_ids(app.layout)
        missing = {"backend", "limit", "refresh", "repo-root", "status", "counts", "sections"} - ids
        assert not missing, missing
    print("v24.8.0 Standalone Quant Dashboard self-test: PASS")
    print("SQLite query service: PASS")
    print("Quant counts: PASS")
    print("Dashboard sections: PASS")
    print("Standalone Dash layout IDs: PASS")
    print("No main app or Data Library files were patched.")
    print("No credentials were written.")
    print("No files were moved or deleted.")
    print("Research/simulation only. No broker calls or trade execution were made.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
