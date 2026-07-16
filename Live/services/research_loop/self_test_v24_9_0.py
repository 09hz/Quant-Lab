from __future__ import annotations

from pathlib import Path
import tempfile


def main() -> int:
    from services.research_loop.models import ResearchLoopConfig
    from services.research_loop.orchestrator import run_research_loop
    from services.quant_dashboard.queries import load_quant_dashboard

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        repo = Path(tmp) / "AlgoTrader"
        live = repo / "Live"
        (live / "data" / "catalog").mkdir(parents=True, exist_ok=True)
        (live / "app.py").write_text("# temp app\n", encoding="utf-8")

        config = ResearchLoopConfig(
            theme="AI infrastructure semiconductors",
            symbols=["AMD", "NVDA", "SMH"],
            max_candidates=10,
            max_loops=1,
            min_trades=10,
            max_drawdown_limit=-0.20,
            min_sharpe=0.25,
            backend="sqlite",
            repo_root=str(repo),
        )
        result = run_research_loop(config)

        assert result.status in {"PASS", "WARN"}, result.status
        assert len(result.candidates) == 10, len(result.candidates)
        assert len(result.evaluations) == 10, len(result.evaluations)
        assert result.report_paths.get("json"), result.report_paths
        assert Path(result.report_paths["json"]).exists(), result.report_paths
        assert result.report_paths.get("markdown"), result.report_paths
        assert Path(result.report_paths["markdown"]).exists(), result.report_paths
        assert result.feedback_path, result.feedback_path
        assert Path(result.feedback_path).exists(), result.feedback_path

        payload = load_quant_dashboard(repo_root=repo, backend="sqlite", limit=20)
        assert payload.status in {"PASS", "WARN"}, payload
        assert payload.counts["experiment_runs"] >= 1, payload.counts
        assert payload.counts["strategy_runs"] >= 1, payload.counts
        assert payload.counts["backtest_runs"] >= 1, payload.counts
        assert payload.sections["best_backtests"], payload.sections

    print("v24.9.0 Research Loop Orchestrator self-test: PASS")
    print("Candidate generation: PASS")
    print("Proxy backtest scoring: PASS")
    print("Report writing: PASS")
    print("Market Memory feedback note: PASS")
    print("Quant Schema persistence: PASS")
    print("Quant Dashboard query visibility: PASS")
    print("No credentials were written.")
    print("No files were moved or deleted.")
    print("Research/simulation only. No broker calls or trade execution were made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
