from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ProcessPoolExecutor, as_completed
import argparse
import json
import sys
import traceback


def _emit_progress(percent: float, stage: str, message: str) -> None:
    clean_stage = str(stage or "running").replace("|", "/")
    clean_message = str(message or "Working...").replace("|", "/")
    print(f"AUTOLAB_PROGRESS|{float(percent):.2f}|{clean_stage}|{clean_message}", flush=True)


def _report_symbol_progress(progress_callback, percent: float, stage: str, message: str) -> None:
    if progress_callback is not None:
        progress_callback(float(percent), str(stage), str(message))


def _bootstrap_import_path() -> Path:
    here = Path(__file__).resolve()
    live_root = here.parents[3]
    repo_root = here.parents[4]
    for path in (str(live_root), str(repo_root)):
        if path not in sys.path:
            sys.path.insert(0, path)
    return live_root


def _parse_symbols(text: str) -> list[str]:
    symbols = []
    for part in (text or "").replace(";", ",").split(","):
        item = part.strip().upper()
        if item and item not in symbols:
            symbols.append(item)
    return symbols


def _run_id() -> str:
    return "universe_" + datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def _candidate_family(candidate_id: str) -> str:
    text = candidate_id or ""
    for token in ("_rsi_", "_fast_", "_slow_", "_buy_thr_", "_sell_thr_"):
        if token in text:
            return text.split(token)[0]
    return text


def _result_rows(run, scorecards) -> list[dict]:
    result_by_key = {(r.candidate_id, r.symbol): r for r in run.results}
    candidate_by_id = {candidate.candidate_id: candidate for candidate in run.candidates}
    rows = []
    for sc in sorted(scorecards, key=lambda item: item.total_score, reverse=True):
        result = result_by_key.get((sc.candidate_id, sc.symbol))
        metrics = dict(getattr(result, "metrics", {}) or {}) if result else {}
        candidate = candidate_by_id.get(sc.candidate_id)
        rows.append(
            {
                "candidate_id": sc.candidate_id,
                "symbol": sc.symbol,
                "strategy_family": _candidate_family(sc.candidate_id),
                "score": sc.total_score,
                "grade": sc.grade,
                "engine_pass": sc.engine_pass,
                "research_pass": sc.research_pass,
                "objective_hit": sc.objective_hit,
                "objective_progress_pct": sc.objective_progress_pct,
                "total_return_pct": metrics.get("total_return_pct", 0.0),
                "max_drawdown_pct": metrics.get("max_drawdown_pct", 0.0),
                "trade_count": metrics.get("trade_count", 0),
                "final_equity": metrics.get("final_equity", 0.0),
                "warnings": list(getattr(sc, "warnings", []) or []),
                "fail_reasons": list(getattr(sc, "fail_reasons", []) or []),
                "name": getattr(candidate, "name", sc.candidate_id),
                "family": getattr(candidate, "family", _candidate_family(sc.candidate_id)),
                "script": getattr(candidate, "script", ""),
                "parameters": dict(getattr(candidate, "parameters", {}) or {}),
                "tags": list(getattr(candidate, "tags", []) or []),
                "source": getattr(candidate, "source", "universe_run"),
                "notes": getattr(candidate, "notes", ""),
            }
        )
    return rows


def _read_text_if_exists(path: Path) -> str:
    try:
        if path.exists():
            return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        pass
    return ""


def _run_symbol_pipeline_uncached(
    *,
    live_root: Path,
    symbol: str,
    args,
    progress_callback=None,
) -> dict:
    from services.ai.auto_lab_orchestrator.models import ExperimentGoal
    from services.ai.auto_lab_orchestrator.orchestrator import AutoLabOrchestrator
    from services.ai.auto_lab_orchestrator.adapters import CoreStrategyBacktestAdapter
    from services.ai.auto_lab_orchestrator.bars_bootstrapper import bootstrap_bars_csv
    from services.ai.auto_lab_orchestrator.data_adapters import load_csv_bars
    from services.ai.auto_lab_orchestrator.seed_library import discover_strategy_seed_candidates
    from services.ai.auto_lab_orchestrator.sizing import SizingConfig, apply_simulation_sizing
    from services.ai.auto_lab_orchestrator.mutator import generate_mutations_for_parents
    from services.ai.auto_lab_orchestrator.execution_quality import normalize_run_execution_quality, write_execution_quality_report
    from services.ai.auto_lab_orchestrator.report_builder import write_run_bundle
    from services.ai.auto_lab_orchestrator.mutation_reporter import write_mutation_artifacts
    from services.ai.auto_lab_orchestrator.real_data_reporter import write_real_data_report
    from services.ai.auto_lab_orchestrator.csv_mutation_retest_sized import write_same_data_baseline_artifacts
    from services.ai.auto_lab_orchestrator.strategy_trace import write_strategy_build_trace_for_report_dir

    _report_symbol_progress(progress_callback, 5, "data", f"Loading historical bars for {symbol}")
    boot = bootstrap_bars_csv(
        live_root=live_root,
        symbol=symbol,
        start=args.start,
        end=args.end,
        timeframe=args.timeframe,
        prefer_local=not args.yfinance_first,
        allow_yfinance=not args.local_only,
    )
    bars, profile = load_csv_bars(
        csv_path=boot.csv_path,
        symbol=symbol,
        start=args.start,
        end=args.end,
    )
    data_profile = profile.to_dict()

    _report_symbol_progress(progress_callback, 15, "baseline", f"Preparing baseline strategies for {symbol}")
    seeds = discover_strategy_seed_candidates(
        live_root=live_root,
        symbol=symbol,
        max_examples=args.max_examples,
        include_built_ins=True,
    )

    sizing_config = SizingConfig(
        sizing_mode=args.sizing_mode,
        cash_exposure_pct=args.cash_exposure_pct,
        fixed_quantity=args.fixed_quantity,
        simulation_only=True,
    )
    initial_cash = float(args.initial_cash)
    target_equity = float(args.target_equity)

    sized_seeds, sizing_info = apply_simulation_sizing(
        seeds,
        bars=bars,
        initial_cash=initial_cash,
        config=sizing_config,
    )

    orchestrator = AutoLabOrchestrator(adapter=CoreStrategyBacktestAdapter(), live_root=live_root)

    baseline_goal = ExperimentGoal(
        question=f"v21.5 multi-symbol same-data baseline for {symbol}.",
        symbols=[symbol],
        timeframe=args.timeframe,
        starting_cash=initial_cash,
        target_equity=target_equity,
        max_drawdown_pct=args.max_drawdown_pct,
        min_trades=1,
        max_runs=len(sized_seeds),
        simulation_only=True,
        notes="Universe runner baseline; simulation-only.",
    )
    _report_symbol_progress(progress_callback, 22, "baseline", f"Running baseline tests for {symbol}")
    baseline_run = orchestrator.run_experiment(
        goal=baseline_goal,
        candidates=sized_seeds,
        bars_by_symbol={symbol: bars},
        write_artifacts=False,
    )
    baseline_run.summary["data_mode"] = "csv_historical_bars"
    baseline_run.summary["universe_runner"] = True
    baseline_run.summary["sizing"] = sizing_info
    baseline_run.summary["data_profile"] = data_profile
    baseline_quality_summary = normalize_run_execution_quality(baseline_run, context=f"{symbol}_universe_baseline")
    write_run_bundle(baseline_run, Path(baseline_run.artifacts["report_md"]).parent)

    baseline_scorecards = list(baseline_run.scorecards)
    baseline_pass_ids = {sc.candidate_id for sc in baseline_scorecards if sc.engine_pass and sc.research_pass}
    eligible_parents = [candidate for candidate in sized_seeds if candidate.candidate_id in baseline_pass_ids]
    eligible_parent_scorecards = [sc for sc in baseline_scorecards if sc.candidate_id in baseline_pass_ids]

    _report_symbol_progress(progress_callback, 42, "mutations", f"Selecting mutation parents for {symbol}")

    if not eligible_parents and not args.strict_parent_gate:
        # Allow engine-pass candidates if none clear research pass, so the universe report still shows why a symbol failed.
        engine_pass_ids = {sc.candidate_id for sc in baseline_scorecards if sc.engine_pass}
        eligible_parents = [candidate for candidate in sized_seeds if candidate.candidate_id in engine_pass_ids]
        eligible_parent_scorecards = [sc for sc in baseline_scorecards if sc.candidate_id in engine_pass_ids]

    mutations = []
    if eligible_parents:
        mutations = generate_mutations_for_parents(
            parents=eligible_parents,
            max_mutations_per_parent=args.max_mutations_per_parent,
            max_total=args.max_total_runs_per_symbol,
            mutate_quantity=args.mutate_quantity,
        )

    if not mutations:
        run_dir = Path(baseline_run.artifacts["report_md"]).parent
        return {
            "symbol": symbol,
            "status": "no_mutations",
            "error": "No mutations generated from eligible baseline parents.",
            "data_source": boot.source,
            "csv_path": boot.csv_path,
            "row_count": data_profile.get("row_count"),
            "first_date": data_profile.get("first_date"),
            "last_date": data_profile.get("last_date"),
            "baseline_run_id": baseline_run.run_id,
            "run_dir": str(run_dir),
            "baseline_research_pass_parents": len(eligible_parents),
            "mutation_count": 0,
            "ranked_mutations": [],
        }

    sized_mutations, mutation_sizing_info = apply_simulation_sizing(
        mutations,
        bars=bars,
        initial_cash=initial_cash,
        config=sizing_config,
    )

    mutation_goal = ExperimentGoal(
        question=f"v21.5 multi-symbol mutation retest for {symbol}.",
        symbols=[symbol],
        timeframe=args.timeframe,
        starting_cash=initial_cash,
        target_equity=target_equity,
        max_drawdown_pct=args.max_drawdown_pct,
        min_trades=1,
        max_runs=len(sized_mutations),
        simulation_only=True,
        notes="Universe runner mutation retest; simulation-only.",
    )
    _report_symbol_progress(progress_callback, 58, "mutations", f"Backtesting mutations for {symbol}")
    run = orchestrator.run_experiment(
        goal=mutation_goal,
        candidates=sized_mutations,
        bars_by_symbol={symbol: bars},
        write_artifacts=False,
    )
    run.summary["data_mode"] = "csv_historical_bars"
    run.summary["universe_runner"] = True
    run.summary["synthetic_vs_real_data"] = "csv_historical_bars"
    run.summary["same_data_baseline"] = True
    run.summary["sizing"] = mutation_sizing_info
    run.summary["data_profile"] = data_profile
    mutation_quality_summary = normalize_run_execution_quality(run, context=f"{symbol}_universe_mutation")
    write_run_bundle(run, Path(run.artifacts["report_md"]).parent)

    settings = {
        "universe_runner": True,
        "symbol": symbol,
        "csv_path": boot.csv_path,
        "data_source": boot.source,
        "start": args.start,
        "end": args.end,
        "max_parent_strategies": args.max_parent_strategies,
        "max_muts_per_parent": args.max_mutations_per_parent,
        "max_total_runs": args.max_total_runs_per_symbol,
        "mutate_quantity": args.mutate_quantity,
        "sizing_mode": args.sizing_mode,
        "cash_exposure_pct": args.cash_exposure_pct,
        "fixed_quantity": args.fixed_quantity,
        "data_mode": "csv_historical_bars",
        "same_data_delta": True,
        "simulation_only": True,
    }

    mutation_artifacts = write_mutation_artifacts(
        run=run,
        parents=eligible_parents,
        parent_scorecards=eligible_parent_scorecards,
        settings=settings,
    )
    run.artifacts.update(mutation_artifacts)

    real_data_artifacts = write_real_data_report(run=run, data_profile=data_profile, settings=settings)
    run.artifacts.update(real_data_artifacts)

    baseline_artifacts = write_same_data_baseline_artifacts(
        baseline_run=baseline_run,
        report_dir=Path(run.artifacts["report_md"]).parent,
        sizing_info=sizing_info,
        data_profile=data_profile,
    )
    run.artifacts.update(baseline_artifacts)

    trace_artifacts = write_strategy_build_trace_for_report_dir(Path(run.artifacts["report_md"]).parent)
    run.artifacts.update(trace_artifacts)

    execution_quality_artifacts = write_execution_quality_report(
        run=run,
        report_dir=Path(run.artifacts["report_md"]).parent,
        normalization_summary={
            "baseline": baseline_quality_summary,
            "mutation": mutation_quality_summary,
        },
    )
    run.artifacts.update(execution_quality_artifacts)

    write_run_bundle(run, Path(run.artifacts["report_md"]).parent)

    ranked_rows = _result_rows(run, run.scorecards)
    run_dir = Path(run.artifacts["report_md"]).parent

    _report_symbol_progress(progress_callback, 92, "artifacts", f"Writing universe reports for {symbol}")

    return {
        "symbol": symbol,
        "status": "ok",
        "data_source": boot.source,
        "csv_path": boot.csv_path,
        "row_count": data_profile.get("row_count"),
        "first_date": data_profile.get("first_date"),
        "last_date": data_profile.get("last_date"),
        "reference_price": mutation_sizing_info.get("reference_price"),
        "example_quantity": mutation_sizing_info.get("example_quantity"),
        "baseline_run_id": baseline_run.run_id,
        "mutation_run_id": run.run_id,
        "run_dir": str(run_dir),
        "baseline_research_pass_parents": len(eligible_parents),
        "mutation_count": len(sized_mutations),
        "research_pass_count": sum(1 for sc in run.scorecards if sc.research_pass),
        "objective_hit_count": sum(1 for sc in run.scorecards if sc.objective_hit),
        "ranked_mutations": ranked_rows,
        "artifacts": dict(run.artifacts),
        "top_strategy_algorithm_text": _read_text_if_exists(run_dir / "top_strategy_algorithm.md"),
    }


def run_symbol_pipeline(*, live_root: Path, symbol: str, args, progress_callback=None) -> dict:
    from services.ai.auto_lab_orchestrator.bars_bootstrapper import bootstrap_bars_csv
    from services.ai.auto_lab_orchestrator.orchestrator import (
        build_exact_result_cache_key,
        load_exact_symbol_result,
        save_exact_symbol_result,
    )

    boot = bootstrap_bars_csv(
        live_root=live_root,
        symbol=symbol,
        start=args.start,
        end=args.end,
        timeframe=args.timeframe,
        prefer_local=not args.yfinance_first,
        allow_yfinance=not args.local_only,
    )
    settings = {
        key: value
        for key, value in vars(args).items()
        if key not in {"run_id", "continue_on_error", "workers", "no_cache"}
    }
    cache_key = build_exact_result_cache_key(
        live_root=live_root,
        kind="universe",
        symbol=symbol,
        csv_path=Path(boot.csv_path),
        settings=settings,
    )
    cached = None if getattr(args, "no_cache", False) else load_exact_symbol_result(live_root=live_root, kind="universe", cache_key=cache_key)
    if cached is not None:
        cached["cache_hit"] = True
        cached["cache_key"] = cache_key
        _report_symbol_progress(progress_callback, 96, "cache_hit", f"Loaded exact cached result for {symbol}")
        return cached
    result = _run_symbol_pipeline_uncached(
        live_root=live_root,
        symbol=symbol,
        args=args,
        progress_callback=progress_callback,
    )
    result["cache_hit"] = False
    result["cache_key"] = cache_key
    if not getattr(args, "no_cache", False):
        save_exact_symbol_result(
            live_root=live_root,
            kind="universe",
            cache_key=cache_key,
            result=result,
        )
    return result


def _run_universe_symbol_worker(live_root_text: str, symbol: str, args_dict: dict) -> dict:
    return run_symbol_pipeline(
        live_root=Path(live_root_text),
        symbol=symbol,
        args=argparse.Namespace(**args_dict),
        progress_callback=None,
    )


def main() -> int:
    live_root = _bootstrap_import_path()

    parser = argparse.ArgumentParser(description="Run Auto Lab across a multi-symbol equity universe.")
    parser.add_argument("--symbols", default="AMD,NVDA,MSFT,AAPL,TSLA")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default="")
    parser.add_argument("--timeframe", default="1d")
    parser.add_argument("--local-only", action="store_true")
    parser.add_argument("--yfinance-first", action="store_true")
    parser.add_argument("--sizing-mode", default="percent_cash_exposure", choices=["fixed_quantity", "max_affordable_shares", "percent_cash_exposure"])
    parser.add_argument("--cash-exposure-pct", type=float, default=95.0)
    parser.add_argument("--fixed-quantity", type=int, default=10)
    parser.add_argument("--initial-cash", type=float, default=12000.0)
    parser.add_argument("--target-equity", type=float, default=24000.0)
    parser.add_argument("--max-drawdown-pct", type=float, default=30.0)
    parser.add_argument("--max-examples", type=int, default=8)
    parser.add_argument("--max-parent-strategies", type=int, default=999)
    parser.add_argument("--max-mutations-per-parent", type=int, default=4)
    parser.add_argument("--max-total-runs-per-symbol", type=int, default=20)
    parser.add_argument("--mutate-quantity", action="store_true")
    parser.add_argument("--strict-parent-gate", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args()

    from services.ai.auto_lab_orchestrator.universe_reporter import build_universe_payload, write_universe_artifacts

    symbols = _parse_symbols(args.symbols)
    if not symbols:
        print("No symbols provided.")
        return 2

    universe_run_id = str(args.run_id or _run_id()).strip()
    if not universe_run_id.replace("-", "").replace("_", "").isalnum():
        print("Invalid run ID. Use letters, numbers, underscores, or hyphens only.")
        return 2
    out_dir = live_root / "data" / "auto_lab_universe_runs" / universe_run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    settings = {
        "symbols": symbols,
        "start": args.start,
        "end": args.end,
        "timeframe": args.timeframe,
        "local_only": args.local_only,
        "yfinance_first": args.yfinance_first,
        "sizing_mode": args.sizing_mode,
        "cash_exposure_pct": args.cash_exposure_pct,
        "fixed_quantity": args.fixed_quantity,
        "initial_cash": args.initial_cash,
        "target_equity": args.target_equity,
        "max_drawdown_pct": args.max_drawdown_pct,
        "max_examples": args.max_examples,
        "max_parent_strategies": args.max_parent_strategies,
        "max_mutations_per_parent": args.max_mutations_per_parent,
        "max_total_runs_per_symbol": args.max_total_runs_per_symbol,
        "mutate_quantity": args.mutate_quantity,
        "workers": min(max(1, int(args.workers or 1)), 4),
        "exact_result_cache": not args.no_cache,
        "simulation_only": True,
    }

    symbol_results = []
    errors = []

    _emit_progress(2, "starting", f"Preparing universe run for {len(symbols)} symbols")
    worker_count = min(max(1, int(args.workers or 1)), 4, len(symbols))
    if worker_count > 1:
        from services.ai.auto_lab_orchestrator.bars_bootstrapper import bootstrap_bars_csv

        for symbol in symbols:
            bootstrap_bars_csv(
                live_root=live_root,
                symbol=symbol,
                start=args.start,
                end=args.end,
                timeframe=args.timeframe,
                prefer_local=not args.yfinance_first,
                allow_yfinance=not args.local_only,
            )
        worker_args = dict(vars(args))
        worker_args["yfinance_first"] = False
        by_symbol = {}
        with ProcessPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(
                    _run_universe_symbol_worker,
                    str(live_root),
                    symbol,
                    worker_args,
                ): symbol
                for symbol in symbols
            }
            for completed_index, future in enumerate(as_completed(futures), start=1):
                symbol = futures[future]
                try:
                    by_symbol[symbol] = future.result()
                except Exception as exc:
                    error = {
                        "symbol": symbol,
                        "status": "error",
                        "error_type": exc.__class__.__name__,
                        "error": str(exc),
                        "traceback": traceback.format_exc(),
                    }
                    by_symbol[symbol] = error
                    errors.append(error)
                _emit_progress(
                    4.0 + (90.0 * completed_index / len(symbols)),
                    "symbol_complete",
                    f"Completed {completed_index}/{len(symbols)} universe symbols",
                )
        symbol_results = [by_symbol[symbol] for symbol in symbols if symbol in by_symbol]
    else:
        for symbol_index, symbol in enumerate(symbols):
            symbol_span = 90.0 / max(1, len(symbols))
            symbol_start = 4.0 + (symbol_index * symbol_span)

            def report_symbol(percent, stage, message, *, _start=symbol_start):
                overall = _start + (symbol_span * max(0.0, min(100.0, float(percent))) / 100.0)
                _emit_progress(overall, stage, message)

            try:
                symbol_results.append(
                    run_symbol_pipeline(live_root=live_root, symbol=symbol, args=args, progress_callback=report_symbol)
                )
            except Exception as exc:
                error = {"symbol": symbol, "status": "error", "error_type": exc.__class__.__name__, "error": str(exc), "traceback": traceback.format_exc()}
                symbol_results.append(error)
                errors.append(error)
                if not args.continue_on_error:
                    break

    _emit_progress(96, "reports", "Building universe leaderboard and reports")
    payload = build_universe_payload(
        universe_run_id=universe_run_id,
        symbols=symbols,
        settings=settings,
        symbol_results=symbol_results,
    )
    artifacts = write_universe_artifacts(payload, out_dir)
    _emit_progress(99, "finalizing", "Finalizing universe research artifacts")

    print("AI Auto Lab universe run complete.")
    print(f"universe_run_id: {universe_run_id}")
    print(f"symbols_requested: {len(symbols)}")
    print(f"symbols_completed: {sum(1 for r in symbol_results if r.get('status') == 'ok')}")
    print(f"errors: {len(errors)}")
    for key, value in artifacts.items():
        print(f"{key}: {value}")

    return 1 if errors and not args.continue_on_error else 0


if __name__ == "__main__":
    raise SystemExit(main())

# BEGIN v24.6 direct producer wiring
try:
    from services.quant_schema.producer_runtime import wire_current_module
    wire_current_module(__name__, globals())
except Exception as _v24_6_direct_wiring_exc:
    print(f"[v24.6 direct producer wiring] disabled for {__name__}: {type(_v24_6_direct_wiring_exc).__name__}: {_v24_6_direct_wiring_exc}")
# END v24.6 direct producer wiring
