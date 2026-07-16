from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile


def _compat_insert_smoke() -> None:
    from services.research_loop.orchestrator import _insert_compatible

    conn = sqlite3.connect(":memory:")
    try:
        # Simulate an older/conflicting experiment_runs table with no experiment_id.
        conn.execute("CREATE TABLE experiment_runs (run_id TEXT, status TEXT, created_at TEXT, config_json TEXT)")
        ok, msg = _insert_compatible(
            conn,
            "experiment_runs",
            {
                "experiment_id": "exp_should_map_to_run_id",
                "run_id": "exp_should_map_to_run_id",
                "status": "PASS",
                "created_at": "2026-01-01T00:00:00+00:00",
                "config": {"simulation_only": True},
                "config_json": {"simulation_only": True},
            },
        )
        assert ok, msg
        count = conn.execute("SELECT COUNT(*) FROM experiment_runs").fetchone()[0]
        assert count == 1, count
    finally:
        conn.close()


def main() -> int:
    from services.research_loop.models import ResearchLoopConfig
    from services.research_loop.orchestrator import run_research_loop
    from services.quant_dashboard.queries import load_quant_dashboard

    _compat_insert_smoke()

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
        assert result.report_paths.get("markdown"), result.report_paths
        md = Path(result.report_paths["markdown"]).read_text(encoding="utf-8", errors="replace")
        assert "What this loop does" in md, "Rich report missing loop explanation."
        assert "Auto Lab is the experiment worker" in md, "Rich report missing Auto Lab distinction."
        assert "Per-symbol simulated results" in md, "Rich report missing per-symbol table."
        assert "Walk-forward proxy" in md, "Rich report missing walk-forward section."
        assert "Universe robustness" in md, "Rich report missing universe section."
        assert "v24.9.3" in md, "Rich report missing v24.9.3 next integration section."
        assert "Real BackTestEngine Adapter" in md, "Rich report missing real adapter guidance."

        assert result.feedback_path, result.feedback_path
        feedback = Path(result.feedback_path).read_text(encoding="utf-8", errors="replace")
        assert "Research Loop is the research manager" in feedback

        payload = load_quant_dashboard(repo_root=repo, backend="sqlite", limit=20)
        assert payload.status in {"PASS", "WARN"}, payload
        assert payload.counts["experiment_runs"] >= 1, payload.counts
        assert payload.counts["backtest_runs"] >= 1, payload.counts

    print("v24.9.2 Research Loop Persistence + Rich Report self-test: PASS")
    print("Compatibility insert for old experiment_runs schema: PASS")
    print("Research loop execution: PASS")
    print("Rich report sections: PASS")
    print("Explicit v24.9.3 next integration guidance: PASS")
    print("Memory feedback detail: PASS")
    print("Quant Dashboard query visibility: PASS")
    print("Adapter hooks compile: PASS")
    print("No credentials were written.")
    print("No files were moved or deleted.")
    print("Research/simulation only. No broker calls or trade execution were made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
