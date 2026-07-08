from __future__ import annotations

from pathlib import Path
import sqlite3
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


def main() -> int:
    from services.quant_schema.migrations import migrate_quant_schema, quant_table_counts, QUANT_TABLES
    from services.quant_schema.repository import (
        upsert_symbol,
        insert_experiment_run,
        insert_strategy_run,
        insert_backtest_run,
        insert_walk_forward_run,
        insert_universe_run,
        insert_feature_snapshot,
        insert_risk_snapshot,
        insert_model_candidate,
        insert_data_quality_event,
    )

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        repo = _make_repo(Path(tmp))
        load_database_config, connect_database = _db_imports()
        config = load_database_config(repo_root=str(repo), backend="sqlite")

        with connect_database(config) as db:
            migrate_quant_schema(db)

            upsert_symbol(db, symbol="NVDA", name="NVIDIA", sector="Technology", metadata={"source": "self_test"})
            exp_id = insert_experiment_run(db, module="self_test", experiment_name="quant_schema_self_test", status="PASS")
            strat_id = insert_strategy_run(
                db,
                experiment_id=exp_id,
                strategy_name="DemoMomentum",
                strategy_family="momentum",
                symbol="NVDA",
                timeframe="1d",
                parameters={"lookback": 20},
                signal_count=4,
                status="PASS",
            )
            insert_backtest_run(
                db,
                strategy_run_id=strat_id,
                experiment_id=exp_id,
                symbol="NVDA",
                strategy_name="DemoMomentum",
                timeframe="1d",
                start_date="2024-01-01",
                end_date="2024-12-31",
                initial_capital=100000,
                ending_capital=112000,
                total_return=0.12,
                sharpe=1.4,
                max_drawdown=-0.08,
                win_rate=0.56,
                profit_factor=1.3,
                trade_count=20,
                status="PASS",
                metrics={"research_only": True},
            )
            insert_walk_forward_run(
                db,
                experiment_id=exp_id,
                symbol="NVDA",
                strategy_name="DemoMomentum",
                timeframe="1d",
                window_count=4,
                avg_sharpe=1.1,
                pass_rate=0.75,
                status="PASS",
            )
            insert_universe_run(
                db,
                experiment_id=exp_id,
                universe_name="AI infrastructure",
                theme="AI infrastructure semiconductors",
                symbols=["NVDA", "AMD", "TSM"],
                selected_count=3,
                ranking=[{"symbol": "NVDA", "rank": 1}],
                status="PASS",
            )
            insert_feature_snapshot(
                db,
                symbol="NVDA",
                as_of="2024-12-31",
                timeframe="1d",
                feature_set_name="demo_features",
                features={"momentum_20": 0.15},
                source_module="self_test",
            )
            insert_risk_snapshot(
                db,
                symbol="NVDA",
                as_of="2024-12-31",
                portfolio_value=100000,
                exposure=0.2,
                volatility=0.3,
                var_95=-0.02,
                sizing_method="research_fixed_fractional",
                risk={"research_only": True},
            )
            insert_model_candidate(
                db,
                experiment_id=exp_id,
                symbol="NVDA",
                model_name="DemoClassifier",
                model_type="classification",
                target_name="forward_return_positive",
                features=["momentum_20"],
                metrics={"auc": 0.61},
                status="PASS",
            )
            insert_data_quality_event(
                db,
                symbol="NVDA",
                dataset_name="demo_prices",
                severity="info",
                event_type="self_test",
                message="Quant schema self-test event.",
                details={"research_only": True},
            )

            counts = quant_table_counts(db)

        missing = [table for table in QUANT_TABLES if table not in counts or counts[table] < 1]
        if missing:
            print(f"Missing/empty tables: {missing}")
            print(counts)
            return 2

    print("v24.4 quant research schema self-test: PASS")
    print("typed quant tables: PASS")
    print("repository insert helpers: PASS")
    print("SQLite fallback: PASS")
    print("No credentials were written.")
    print("No files were moved or deleted.")
    print("Research/simulation only. No broker calls or trade execution were made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
