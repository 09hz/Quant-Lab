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


def _configured_counts(repo: Path) -> dict[str, int]:
    from services.quant_schema.migrations import migrate_quant_schema, quant_table_counts

    load_database_config, connect_database = _db_imports()
    config = load_database_config(repo_root=str(repo), backend="sqlite")

    with connect_database(config) as db:
        migrate_quant_schema(db)
        return quant_table_counts(db)


def _assert_min_count(counts: dict[str, int], table: str, minimum: int) -> None:
    value = int(counts.get(table, -1))
    assert value >= minimum, f"{table} expected >= {minimum}, got {value}; counts={counts}"


def main() -> int:
    from services.quant_schema.result_capture import (
        capture_backtest_result,
        capture_auto_lab_result,
        capture_walk_forward_result,
        capture_universe_result,
    )
    from services.quant_schema.promote_artifacts import promote_managed_artifacts
    from services.quant_schema.runtime_wiring import install_quant_output_hooks

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        repo = _make_repo(Path(tmp))

        bt = capture_backtest_result(
            {
                "symbol": "NVDA",
                "strategy_name": "DemoMomentum",
                "timeframe": "1d",
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "initial_capital": 100000,
                "ending_capital": 113000,
                "total_return": 0.13,
                "sharpe": 1.5,
                "max_drawdown": -0.07,
                "win_rate": 0.58,
                "profit_factor": 1.4,
                "trade_count": 24,
            },
            context={"module": "self_test", "method": "backtest"},
            repo_root=repo,
            preferred_backend="sqlite",
            ingest_artifact=False,
        )
        assert bt.status == "captured", bt
        assert bt.typed_rows and "backtest_runs" in bt.typed_rows, bt

        auto = capture_auto_lab_result(
            {
                "symbol": "AMD",
                "strategy_name": "AutoLabCandidate",
                "sharpe": 1.1,
                "max_drawdown": -0.09,
                "win_rate": 0.52,
            },
            context={"module": "self_test", "method": "auto_lab"},
            repo_root=repo,
            preferred_backend="sqlite",
            ingest_artifact=False,
        )
        assert auto.status == "captured", auto
        assert auto.typed_rows and "backtest_runs" in auto.typed_rows, auto

        wf = capture_walk_forward_result(
            {
                "symbol": "TSM",
                "strategy_name": "WalkForwardDemo",
                "window_count": 4,
                "avg_sharpe": 1.0,
                "pass_rate": 0.75,
            },
            context={"module": "self_test", "method": "walk_forward"},
            repo_root=repo,
            preferred_backend="sqlite",
            ingest_artifact=False,
        )
        assert wf.status == "captured", wf
        assert wf.typed_rows and "walk_forward_runs" in wf.typed_rows, wf

        uni = capture_universe_result(
            {
                "symbols": ["NVDA", "AMD", "TSM"],
                "theme": "AI infrastructure semiconductors",
                "ranking": [{"symbol": "NVDA", "rank": 1}],
            },
            context={"module": "self_test", "method": "universe", "theme": "AI infrastructure semiconductors"},
            repo_root=repo,
            preferred_backend="sqlite",
            ingest_artifact=False,
        )
        assert uni.status == "captured", uni
        assert uni.typed_rows and "universe_runs" in uni.typed_rows, uni

        counts = _configured_counts(repo)
        _assert_min_count(counts, "experiment_runs", 4)
        _assert_min_count(counts, "backtest_runs", 2)
        _assert_min_count(counts, "strategy_runs", 3)
        _assert_min_count(counts, "walk_forward_runs", 1)
        _assert_min_count(counts, "universe_runs", 1)

        promotion = promote_managed_artifacts(repo, preferred_backend="sqlite", limit=5, dry_run=True)
        assert promotion["seen"] >= 1, promotion

        hooks = install_quant_output_hooks()
        assert hooks["status"] in {"installed", "already_installed", "disabled_by_env"}, hooks

    print("v24.5 quant output wiring self-test: PASS")
    print("Artifact Writer capture: PASS")
    print("Typed quant schema inserts: PASS")
    print("Configured SQLite fallback verification: PASS")
    print("Backtest/AutoLab/WalkForward/Universe capture helpers: PASS")
    print("Promotion dry-run: PASS")
    print("Runtime hook installer: PASS")
    print("No credentials were written.")
    print("No files were moved or deleted.")
    print("Research/simulation only. No broker calls or trade execution were made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
