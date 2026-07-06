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
    run_dir = live_root / "data" / "auto_lab_runs" / "_strategy_trace_self_test"
    run_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "settings": {
            "sizing_mode": "percent_cash_exposure",
            "cash_exposure_pct": 95,
            "simulation_only": True,
        },
        "parents": [
            {
                "candidate_id": "example_rsi_mean_reversion",
                "name": "RSI Mean Reversion",
                "script": "r = ta.rsi(close, 14)\nbuy when ta.crossunder(r, 30)\nsell when ta.crossover(r, 70)",
                "parameters": {"quantity": 114},
                "source": "self_test",
            }
        ],
        "parent_scorecards": [
            {
                "candidate_id": "example_rsi_mean_reversion",
                "symbol": "AMD",
                "total_score": 77.54,
                "grade": "B",
                "engine_pass": True,
                "research_pass": True,
                "objective_hit": False,
                "objective_progress_pct": 26.39,
                "component_scores": {"return_score": 6.6},
            }
        ],
        "run": {
            "run_id": "_strategy_trace_self_test",
            "summary": {
                "data_profile": {
                    "symbol": "AMD",
                    "data_mode": "csv_historical_bars",
                    "row_count": 260,
                }
            },
            "candidates": [
                {
                    "candidate_id": "example_rsi_mean_reversion_rsi_14_to_17",
                    "name": "RSI Mean Reversion rsi 14 to 17",
                    "script": "r = ta.rsi(close, 17)\nbuy when ta.crossunder(r, 30)\nsell when ta.crossover(r, 70)",
                    "parameters": {"quantity": 114, "generation": 1, "parent_id": "example_rsi_mean_reversion"},
                    "source": "mutation_of:example_rsi_mean_reversion",
                }
            ],
            "scorecards": [
                {
                    "candidate_id": "example_rsi_mean_reversion_rsi_14_to_17",
                    "symbol": "AMD",
                    "total_score": 86.22,
                    "grade": "A",
                    "engine_pass": True,
                    "research_pass": True,
                    "objective_hit": False,
                    "objective_progress_pct": 44.88,
                    "component_scores": {"return_score": 11.2, "drawdown_score": 20},
                    "warnings": ["Target objective not hit."],
                    "fail_reasons": [],
                }
            ],
            "results": [
                {
                    "candidate_id": "example_rsi_mean_reversion_rsi_14_to_17",
                    "symbol": "AMD",
                    "metrics": {
                        "initial_cash": 12000,
                        "final_equity": 17385.43,
                        "total_return_pct": 44.88,
                        "max_drawdown_pct": 0.0,
                        "trade_count": 4,
                        "win_rate_pct": 100,
                        "profit_factor": 10.0,
                    },
                }
            ],
        },
    }
    (run_dir / "mutation_results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    from services.ai.auto_lab_orchestrator.strategy_trace import write_strategy_build_trace_for_report_dir

    artifacts = write_strategy_build_trace_for_report_dir(run_dir)
    for key, value in artifacts.items():
        assert Path(value).exists(), f"Missing artifact {key}: {value}"

    data = json.loads(Path(artifacts["strategy_build_trace_json"]).read_text(encoding="utf-8"))
    assert data["trace_count"] == 1, "Expected one trace"
    assert data["traces"][0]["mutation"]["type"] == "rsi_length", "Expected RSI mutation inference"

    print("AI Auto Lab strategy trace self-test: PASS")
    for key, value in artifacts.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
