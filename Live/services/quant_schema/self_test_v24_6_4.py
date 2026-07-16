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


def main() -> int:
    from services.quant_schema.result_capture import capture_backtest_result, _safe_json
    from services.quant_schema import runtime_wiring

    old_env = {key: os.environ.get(key) for key in [
        "ALGOTRADER_ENABLE_QUANT_WIRING",
        "ALGOTRADER_ENABLE_BROAD_RUNTIME_HOOKS",
        "ALGOTRADER_ARTIFACT_POSTGRES_INGEST",
        "ALGOTRADER_DB_BACKEND",
        "ALGOTRADER_DB_PASSWORD",
        "ALGOTRADER_DATABASE_URL",
    ]}

    try:
        os.environ["ALGOTRADER_ARTIFACT_POSTGRES_INGEST"] = "0"
        for key in ["ALGOTRADER_DB_BACKEND", "ALGOTRADER_DB_PASSWORD", "ALGOTRADER_DATABASE_URL"]:
            os.environ.pop(key, None)

        os.environ.pop("ALGOTRADER_ENABLE_BROAD_RUNTIME_HOOKS", None)
        os.environ["ALGOTRADER_ENABLE_QUANT_WIRING"] = "1"
        assert runtime_wiring._enabled() is False, "Broad runtime hooks should be off by default."

        os.environ["ALGOTRADER_ENABLE_BROAD_RUNTIME_HOOKS"] = "1"
        assert runtime_wiring._enabled() is True, "Broad runtime hooks should be explicitly opt-in."

        cyclic = {"symbol": "NVDA"}
        cyclic["self"] = cyclic
        safe = _safe_json(cyclic)
        assert safe["self"] == "<recursive_ref>", safe

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            repo = _make_repo(Path(tmp))
            result = capture_backtest_result(
                {
                    "symbol": "NVDA",
                    "strategy_name": "RecursionGuardProbe",
                    "sharpe": 1.0,
                    "max_drawdown": -0.05,
                    "win_rate": 0.55,
                    "cycle": cyclic,
                },
                context={"module": "self_test", "method": "recursion_guard_probe"},
                repo_root=repo,
                preferred_backend="sqlite",
                ingest_artifact=False,
            )
            assert result.status in {"captured", "artifact_only"}, result

    finally:
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    print("v24.6.4 runtime wiring recursion guard self-test: PASS")
    print("broad runtime hooks default-off: PASS")
    print("explicit broad hook opt-in: PASS")
    print("recursive JSON serialization guard: PASS")
    print("capture recursion guard path: PASS")
    print("No credentials were written.")
    print("No files were moved or deleted.")
    print("Research/simulation only. No broker calls or trade execution were made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
