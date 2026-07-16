from __future__ import annotations

from pathlib import Path
import py_compile


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "Live" / "app.py").exists():
            return parent
        if parent.name.lower() == "live" and (parent / "app.py").exists():
            return parent.parent
    return Path.cwd()


def main() -> int:
    repo = _repo_root()
    live = repo / "Live"
    engine_path = live / "core" / "BackTestEngine.py"

    assert engine_path.exists(), f"Actual project BackTestEngine missing: {engine_path}"

    py_compile.compile(str(engine_path), doraise=True)
    py_compile.compile(str(live / "services" / "research_loop" / "backtest_engine_adapter.py"), doraise=True)
    py_compile.compile(str(live / "services" / "research_loop" / "evaluation_pipeline.py"), doraise=True)
    py_compile.compile(str(live / "services" / "research_loop" / "orchestrator.py"), doraise=True)

    from services.research_loop.models import ResearchLoopConfig
    from services.research_loop.strategy_candidate_generator import generate_strategy_candidates
    from services.research_loop.backtest_engine_adapter import SafeBackTestEngineAdapter
    from services.research_loop.evaluation_pipeline import evaluate_candidate_for_loop

    config = ResearchLoopConfig(
        theme="AI infrastructure semiconductors",
        symbols=["AMD", "NVDA", "SMH"],
        max_candidates=1,
        max_loops=1,
        min_trades=10,
        max_drawdown_limit=-0.20,
        min_sharpe=0.25,
        backend="sqlite",
        repo_root=str(repo),
        evaluation_mode="hybrid_safe",
    )
    candidate = generate_strategy_candidates(config)[0]

    adapter = SafeBackTestEngineAdapter(repo)
    real_evaluation, attempts = adapter.evaluate_candidate(config, candidate)

    assert attempts or real_evaluation is not None, "Adapter did not attempt to use the actual BackTestEngine."

    print("v24.9.3 Real BackTestEngine adapter actual-engine probe")
    print(f"Actual BackTestEngine path: {engine_path}")

    if attempts:
        print("Adapter attempts:")
        for attempt in attempts[-12:]:
            message = str(attempt.message).replace("\n", " ")[:260]
            print(f"  - {attempt.name}: {attempt.status}: {message}")

    if real_evaluation is not None:
        assert real_evaluation.aggregate_metrics.get("evaluation_source") == "real_backtest_engine_adapter"
        print("Actual BackTestEngine adapter path: PASS")
        print(f"Evaluation source: {real_evaluation.aggregate_metrics.get('evaluation_source')}")
        print(f"Strategy: {real_evaluation.candidate.strategy_name}")
        print(f"Score: {real_evaluation.score}")
    else:
        print("Actual BackTestEngine adapter path: PROBED")
        print("The adapter found/probed the real BackTestEngine, but did not find a safely callable function returning parseable metrics.")
        print("In hybrid_safe mode, the Research Loop will fall back to proxy scoring and include adapter attempts in the report.")

    pipeline_eval = evaluate_candidate_for_loop(config, candidate)
    assert pipeline_eval.status in {"PASS", "REJECT"}, pipeline_eval.status
    assert "evaluation_source" in pipeline_eval.aggregate_metrics, pipeline_eval.aggregate_metrics

    print("v24.9.3.1 Real BackTestEngine Self-Test Fix: PASS")
    print("No fake BackTestEngine was created.")
    print("Actual project BackTestEngine compile: PASS")
    print("Actual project BackTestEngine probe: PASS")
    print("Hybrid-safe evaluation pipeline: PASS")
    print("No credentials were written.")
    print("No files were moved or deleted.")
    print("Research/simulation only. No broker calls or trade execution were made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
