from __future__ import annotations

import os
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


def _counts(repo: Path) -> dict[str, int]:
    from services.quant_schema.migrations import migrate_quant_schema, quant_table_counts
    load_database_config, connect_database = _db_imports()
    config = load_database_config(repo_root=str(repo), backend="sqlite")
    with connect_database(config) as db:
        migrate_quant_schema(db)
        return quant_table_counts(db)


def main() -> int:
    from services.quant_schema.producer_runtime import infer_category, wire_namespace
    from services.quant_schema.direct_producer_wiring import install_direct_producer_wiring
    from services.quant_schema.result_capture import capture_backtest_result

    saved_env = {key: os.environ.get(key) for key in [
        "ALGOTRADER_DB_BACKEND",
        "ALGOTRADER_DB_PASSWORD",
        "ALGOTRADER_DATABASE_URL",
        "ALGOTRADER_ARTIFACT_POSTGRES_INGEST",
    ]}
    try:
        # Make this self-test deterministic. Real runtime can still auto-select
        # PostgreSQL when credentials are present.
        os.environ["ALGOTRADER_ARTIFACT_POSTGRES_INGEST"] = "0"
        for key in ["ALGOTRADER_DB_BACKEND", "ALGOTRADER_DB_PASSWORD", "ALGOTRADER_DATABASE_URL"]:
            os.environ.pop(key, None)

        assert infer_category("core.BackTestEngine", "run_backtest") == "backtest"
        assert infer_category("core.BackTestEngine", "run_universe") == "universe"
        assert infer_category("services.ai.auto_lab_orchestrator.universe_runner", "run_universe") == "universe"
        assert infer_category("services.ai.market_memory.research_packet", "build_research_packet") == "market_memory"

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            repo = _make_repo(Path(tmp))

            direct_capture = capture_backtest_result(
                {
                    "symbol": "MSFT",
                    "strategy_name": "DirectCaptureProbe",
                    "sharpe": 1.0,
                    "max_drawdown": -0.04,
                    "win_rate": 0.55,
                },
                context={"module": "self_test", "method": "direct_capture_probe"},
                repo_root=repo,
                preferred_backend="sqlite",
                ingest_artifact=False,
            )
            assert direct_capture.status == "captured", direct_capture
            counts_after_direct = _counts(repo)
            assert counts_after_direct["backtest_runs"] >= 1, counts_after_direct

            def run_backtest():
                return {
                    "symbol": "NVDA",
                    "strategy_name": "DirectWireDemo",
                    "timeframe": "1d",
                    "sharpe": 1.7,
                    "max_drawdown": -0.06,
                    "win_rate": 0.61,
                    "profit_factor": 1.5,
                    "trade_count": 18,
                }

            def run_universe():
                return {
                    "symbols": ["NVDA", "AMD", "TSM"],
                    "theme": "AI infrastructure semiconductors",
                    "ranking": [{"symbol": "NVDA", "rank": 1}],
                }

            class DemoBackTestEngine:
                def execute_backtest(self):
                    return {
                        "symbol": "AMD",
                        "strategy_name": "ClassDirectWireDemo",
                        "sharpe": 1.2,
                        "max_drawdown": -0.08,
                        "win_rate": 0.54,
                    }

            run_backtest.__module__ = "core.BackTestEngine"
            run_universe.__module__ = "core.BackTestEngine"
            DemoBackTestEngine.__module__ = "core.BackTestEngine"
            DemoBackTestEngine.execute_backtest.__module__ = "core.BackTestEngine"

            ns = {
                "run_backtest": run_backtest,
                "run_universe": run_universe,
                "DemoBackTestEngine": DemoBackTestEngine,
            }

            result = wire_namespace("core.BackTestEngine", ns, repo_root=repo, preferred_backend="sqlite")
            assert result["status"] == "wired", result
            assert result["wrapped"] >= 3, result

            original = ns["run_backtest"]()
            assert original["symbol"] == "NVDA"

            universe = ns["run_universe"]()
            assert universe["symbols"][0] == "NVDA"

            class_result = DemoBackTestEngine().execute_backtest()
            assert class_result["symbol"] == "AMD"

            counts = _counts(repo)
            assert counts["backtest_runs"] >= 3, counts
            assert counts["strategy_runs"] >= 3, counts
            assert counts["universe_runs"] >= 1, counts
            assert counts["experiment_runs"] >= 4, counts

            installer_result = install_direct_producer_wiring()
            assert installer_result["status"] in {"installed", "already_installed", "disabled"}, installer_result

    finally:
        for key, value in saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    print("v24.6 direct producer wiring self-test: PASS")
    print("direct capture probe: PASS")
    print("category inference: PASS")
    print("function wrapping: PASS")
    print("class method wrapping: PASS")
    print("Artifact Writer capture path: PASS")
    print("Typed quant schema rows: PASS")
    print("forced SQLite test backend: PASS")
    print("global installer: PASS")
    print("No credentials were written.")
    print("No files were moved or deleted.")
    print("Research/simulation only. No broker calls or trade execution were made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
