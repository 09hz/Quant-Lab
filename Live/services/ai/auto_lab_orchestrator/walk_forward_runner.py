from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import argparse
import math
import sys
import traceback


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
    return "walk_forward_" + datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def _safe_float(value, default=0.0) -> float:
    try:
        if value is None:
            return default
        out = float(value)
        if math.isnan(out) or math.isinf(out):
            return default
        return out
    except Exception:
        return default


def _first_close(bars) -> float:
    try:
        if hasattr(bars, "columns") and "close" in bars.columns:
            s = bars["close"].dropna()
            return _safe_float(s.iloc[0], 0.0) if len(s) else 0.0
        for row in bars:
            if isinstance(row, dict):
                close = _safe_float(row.get("close"), 0.0)
            else:
                close = _safe_float(getattr(row, "close", 0.0), 0.0)
            if close > 0:
                return close
    except Exception:
        pass
    return 0.0


def _last_close(bars) -> float:
    try:
        if hasattr(bars, "columns") and "close" in bars.columns:
            s = bars["close"].dropna()
            return _safe_float(s.iloc[-1], 0.0) if len(s) else 0.0
        last = 0.0
        for row in bars:
            if isinstance(row, dict):
                close = _safe_float(row.get("close"), 0.0)
            else:
                close = _safe_float(getattr(row, "close", 0.0), 0.0)
            if close > 0:
                last = close
        return last
    except Exception:
        pass
    return 0.0


def buy_hold_return_pct(bars) -> float:
    first = _first_close(bars)
    last = _last_close(bars)
    if first <= 0 or last <= 0:
        return 0.0
    return ((last / first) - 1.0) * 100.0


def _result_by_key(run):
    return {(r.candidate_id, r.symbol): r for r in run.results}


def _candidate_by_id(candidates):
    return {c.candidate_id: c for c in candidates}


def _row_from_train_test(symbol, train_sc, test_sc, test_result, candidate, buy_hold_test):
    metrics = dict(getattr(test_result, "metrics", {}) or {}) if test_result else {}
    from services.ai.auto_lab_orchestrator.walk_forward_reporter import overfit_label

    label = overfit_label(
        train_progress=getattr(train_sc, "objective_progress_pct", 0.0),
        test_progress=getattr(test_sc, "objective_progress_pct", 0.0),
        train_hit=getattr(train_sc, "objective_hit", False),
        test_hit=getattr(test_sc, "objective_hit", False),
    )

    return {
        "symbol": symbol,
        "candidate_id": getattr(test_sc, "candidate_id", ""),
        "script": getattr(candidate, "script", ""),
        "train_score": getattr(train_sc, "total_score", 0.0),
        "test_score": getattr(test_sc, "total_score", 0.0),
        "train_grade": getattr(train_sc, "grade", ""),
        "test_grade": getattr(test_sc, "grade", ""),
        "train_engine_pass": getattr(train_sc, "engine_pass", False),
        "test_engine_pass": getattr(test_sc, "engine_pass", False),
        "train_research_pass": getattr(train_sc, "research_pass", False),
        "test_research_pass": getattr(test_sc, "research_pass", False),
        "train_objective_hit": getattr(train_sc, "objective_hit", False),
        "test_objective_hit": getattr(test_sc, "objective_hit", False),
        "train_objective_progress_pct": getattr(train_sc, "objective_progress_pct", 0.0),
        "test_objective_progress_pct": getattr(test_sc, "objective_progress_pct", 0.0),
        "test_total_return_pct": metrics.get("total_return_pct", 0.0),
        "test_final_equity": metrics.get("final_equity", 0.0),
        "test_max_drawdown_pct": metrics.get("max_drawdown_pct", 0.0),
        "test_trade_count": metrics.get("trade_count", 0),
        "test_win_rate_pct": metrics.get("win_rate_pct", 0.0),
        "buy_hold_test_return_pct": buy_hold_test,
        "overfit_label": label,
        "test_warnings": list(getattr(test_sc, "warnings", []) or []),
        "test_fail_reasons": list(getattr(test_sc, "fail_reasons", []) or []),
    }


def run_symbol_walk_forward(*, live_root: Path, symbol: str, args) -> dict:
    from services.ai.auto_lab_orchestrator.models import ExperimentGoal
    from services.ai.auto_lab_orchestrator.orchestrator import AutoLabOrchestrator
    from services.ai.auto_lab_orchestrator.adapters import CoreStrategyBacktestAdapter
    from services.ai.auto_lab_orchestrator.bars_bootstrapper import bootstrap_bars_csv
    from services.ai.auto_lab_orchestrator.data_adapters import load_csv_bars
    from services.ai.auto_lab_orchestrator.seed_library import discover_strategy_seed_candidates
    from services.ai.auto_lab_orchestrator.sizing import SizingConfig, apply_simulation_sizing
    from services.ai.auto_lab_orchestrator.mutator import generate_mutations_for_parents
    from services.ai.auto_lab_orchestrator.execution_quality import normalize_run_execution_quality
    from services.ai.auto_lab_orchestrator.report_builder import write_run_bundle

    boot = bootstrap_bars_csv(
        live_root=live_root,
        symbol=symbol,
        start=args.train_start,
        end=args.test_end,
        timeframe=args.timeframe,
        prefer_local=not args.yfinance_first,
        allow_yfinance=not args.local_only,
    )

    train_bars, train_profile = load_csv_bars(
        csv_path=boot.csv_path,
        symbol=symbol,
        start=args.train_start,
        end=args.train_end,
    )
    test_bars, test_profile = load_csv_bars(
        csv_path=boot.csv_path,
        symbol=symbol,
        start=args.test_start,
        end=args.test_end,
    )

    train_buy_hold = buy_hold_return_pct(train_bars)
    test_buy_hold = buy_hold_return_pct(test_bars)

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

    sized_seeds_train, train_seed_sizing = apply_simulation_sizing(
        seeds,
        bars=train_bars,
        initial_cash=initial_cash,
        config=sizing_config,
    )

    orchestrator = AutoLabOrchestrator(adapter=CoreStrategyBacktestAdapter(), live_root=live_root)

    baseline_goal = ExperimentGoal(
        question=f"v21.6 walk-forward TRAIN baseline for {symbol}.",
        symbols=[symbol],
        timeframe=args.timeframe,
        starting_cash=initial_cash,
        target_equity=target_equity,
        max_drawdown_pct=args.max_drawdown_pct,
        min_trades=1,
        max_runs=len(sized_seeds_train),
        simulation_only=True,
        notes="Walk-forward train baseline; simulation-only.",
    )
    baseline_run = orchestrator.run_experiment(
        goal=baseline_goal,
        candidates=sized_seeds_train,
        bars_by_symbol={symbol: train_bars},
    )
    baseline_run.summary["walk_forward_phase"] = "train_baseline"
    baseline_run.summary["data_profile"] = train_profile.to_dict()
    baseline_run.summary["sizing"] = train_seed_sizing
    normalize_run_execution_quality(baseline_run, context=f"{symbol}_train_baseline")
    write_run_bundle(baseline_run, Path(baseline_run.artifacts["report_md"]).parent)

    baseline_pass_ids = {sc.candidate_id for sc in baseline_run.scorecards if sc.engine_pass and sc.research_pass}
    eligible_parents = [c for c in sized_seeds_train if c.candidate_id in baseline_pass_ids]
    if not eligible_parents and not args.strict_parent_gate:
        engine_pass_ids = {sc.candidate_id for sc in baseline_run.scorecards if sc.engine_pass}
        eligible_parents = [c for c in sized_seeds_train if c.candidate_id in engine_pass_ids]

    mutations = []
    if eligible_parents:
        mutations = generate_mutations_for_parents(
            parents=eligible_parents,
            max_mutations_per_parent=args.max_mutations_per_parent,
            max_total=args.max_total_runs_per_symbol,
            mutate_quantity=args.mutate_quantity,
        )

    if not mutations:
        return {
            "symbol": symbol,
            "status": "no_train_mutations",
            "data_source": boot.source,
            "csv_path": boot.csv_path,
            "train_rows": train_profile.row_count,
            "test_rows": test_profile.row_count,
            "buy_hold_train_return_pct": train_buy_hold,
            "buy_hold_test_return_pct": test_buy_hold,
            "validated_candidates": [],
        }

    sized_mutations_train, train_mutation_sizing = apply_simulation_sizing(
        mutations,
        bars=train_bars,
        initial_cash=initial_cash,
        config=sizing_config,
    )

    train_goal = ExperimentGoal(
        question=f"v21.6 walk-forward TRAIN mutation retest for {symbol}.",
        symbols=[symbol],
        timeframe=args.timeframe,
        starting_cash=initial_cash,
        target_equity=target_equity,
        max_drawdown_pct=args.max_drawdown_pct,
        min_trades=1,
        max_runs=len(sized_mutations_train),
        simulation_only=True,
        notes="Walk-forward train mutation retest; simulation-only.",
    )
    train_run = orchestrator.run_experiment(
        goal=train_goal,
        candidates=sized_mutations_train,
        bars_by_symbol={symbol: train_bars},
    )
    train_run.summary["walk_forward_phase"] = "train_mutation"
    train_run.summary["data_profile"] = train_profile.to_dict()
    train_run.summary["sizing"] = train_mutation_sizing
    normalize_run_execution_quality(train_run, context=f"{symbol}_train_mutation")
    write_run_bundle(train_run, Path(train_run.artifacts["report_md"]).parent)

    train_candidates_by_id = _candidate_by_id(sized_mutations_train)
    train_scorecards_sorted = sorted(train_run.scorecards, key=lambda sc: sc.total_score, reverse=True)
    train_selected = [sc for sc in train_scorecards_sorted if sc.engine_pass and sc.research_pass][: args.top_n_per_symbol]
    if len(train_selected) < args.top_n_per_symbol:
        extra = [sc for sc in train_scorecards_sorted if sc.engine_pass and sc not in train_selected]
        train_selected += extra[: max(0, args.top_n_per_symbol - len(train_selected))]

    selected_candidates = [train_candidates_by_id[sc.candidate_id] for sc in train_selected if sc.candidate_id in train_candidates_by_id]
    if not selected_candidates:
        return {
            "symbol": symbol,
            "status": "no_train_selected",
            "data_source": boot.source,
            "csv_path": boot.csv_path,
            "train_rows": train_profile.row_count,
            "test_rows": test_profile.row_count,
            "buy_hold_train_return_pct": train_buy_hold,
            "buy_hold_test_return_pct": test_buy_hold,
            "validated_candidates": [],
        }

    sized_test_candidates, test_sizing = apply_simulation_sizing(
        selected_candidates,
        bars=test_bars,
        initial_cash=initial_cash,
        config=sizing_config,
    )

    test_goal = ExperimentGoal(
        question=f"v21.6 walk-forward TEST validation for {symbol}.",
        symbols=[symbol],
        timeframe=args.timeframe,
        starting_cash=initial_cash,
        target_equity=target_equity,
        max_drawdown_pct=args.max_drawdown_pct,
        min_trades=1,
        max_runs=len(sized_test_candidates),
        simulation_only=True,
        notes="Walk-forward unseen test validation; simulation-only.",
    )
    test_run = orchestrator.run_experiment(
        goal=test_goal,
        candidates=sized_test_candidates,
        bars_by_symbol={symbol: test_bars},
    )
    test_run.summary["walk_forward_phase"] = "test_validation"
    test_run.summary["data_profile"] = test_profile.to_dict()
    test_run.summary["sizing"] = test_sizing
    normalize_run_execution_quality(test_run, context=f"{symbol}_test_validation")
    write_run_bundle(test_run, Path(test_run.artifacts["report_md"]).parent)

    train_sc_by_id = {sc.candidate_id: sc for sc in train_run.scorecards}
    test_result_by_key = _result_by_key(test_run)
    test_candidate_by_id = _candidate_by_id(sized_test_candidates)

    rows = []
    for test_sc in sorted(test_run.scorecards, key=lambda sc: sc.total_score, reverse=True):
        train_sc = train_sc_by_id.get(test_sc.candidate_id)
        candidate = test_candidate_by_id.get(test_sc.candidate_id)
        test_result = test_result_by_key.get((test_sc.candidate_id, test_sc.symbol))
        if train_sc and candidate:
            rows.append(_row_from_train_test(symbol, train_sc, test_sc, test_result, candidate, test_buy_hold))

    best = rows[0] if rows else {}

    return {
        "symbol": symbol,
        "status": "ok",
        "data_source": boot.source,
        "csv_path": boot.csv_path,
        "train_rows": train_profile.row_count,
        "test_rows": test_profile.row_count,
        "train_first_date": train_profile.first_date,
        "train_last_date": train_profile.last_date,
        "test_first_date": test_profile.first_date,
        "test_last_date": test_profile.last_date,
        "buy_hold_train_return_pct": train_buy_hold,
        "buy_hold_test_return_pct": test_buy_hold,
        "baseline_run_id": baseline_run.run_id,
        "train_run_id": train_run.run_id,
        "test_run_id": test_run.run_id,
        "train_run_dir": str(Path(train_run.artifacts["report_md"]).parent),
        "test_run_dir": str(Path(test_run.artifacts["report_md"]).parent),
        "train_research_pass_candidates": sum(1 for sc in train_run.scorecards if sc.research_pass),
        "validated_candidates": rows,
        "best_candidate_id": best.get("candidate_id", ""),
        "best_train_score": best.get("train_score", 0.0),
        "best_test_score": best.get("test_score", 0.0),
        "best_train_objective_hit": best.get("train_objective_hit", False),
        "best_test_objective_hit": best.get("test_objective_hit", False),
        "best_test_objective_progress_pct": best.get("test_objective_progress_pct", 0.0),
        "best_overfit_label": best.get("overfit_label", ""),
    }


def main() -> int:
    live_root = _bootstrap_import_path()

    parser = argparse.ArgumentParser(description="Run multi-symbol walk-forward validation.")
    parser.add_argument("--symbols", default="AMD,NVDA,MSFT,AAPL,TSLA")
    parser.add_argument("--train-start", default="2020-01-01")
    parser.add_argument("--train-end", default="2023-12-31")
    parser.add_argument("--test-start", default="2024-01-01")
    parser.add_argument("--test-end", default="2025-12-31")
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
    parser.add_argument("--max-mutations-per-parent", type=int, default=4)
    parser.add_argument("--max-total-runs-per-symbol", type=int, default=20)
    parser.add_argument("--top-n-per-symbol", type=int, default=3)
    parser.add_argument("--mutate-quantity", action="store_true")
    parser.add_argument("--strict-parent-gate", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    args = parser.parse_args()

    from services.ai.auto_lab_orchestrator.walk_forward_reporter import build_walk_forward_payload, write_walk_forward_artifacts

    symbols = _parse_symbols(args.symbols)
    if not symbols:
        print("No symbols provided.")
        return 2

    run_id = _run_id()
    out_dir = live_root / "data" / "auto_lab_walk_forward_runs" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    settings = {
        "symbols": symbols,
        "validation_mode": "single_train_test_split",
        "train_start": args.train_start,
        "train_end": args.train_end,
        "test_start": args.test_start,
        "test_end": args.test_end,
        "timeframe": args.timeframe,
        "local_only": args.local_only,
        "yfinance_first": args.yfinance_first,
        "sizing_mode": args.sizing_mode,
        "cash_exposure_pct": args.cash_exposure_pct,
        "fixed_quantity": args.fixed_quantity,
        "initial_cash": args.initial_cash,
        "target_equity": args.target_equity,
        "max_drawdown_pct": args.max_drawdown_pct,
        "top_n_per_symbol": args.top_n_per_symbol,
        "max_mutations_per_parent": args.max_mutations_per_parent,
        "max_total_runs_per_symbol": args.max_total_runs_per_symbol,
        "benchmark": "buy_and_hold_return_pct",
        "simulation_only": True,
    }

    results = []
    errors = []

    for symbol in symbols:
        print(f"=== Walk-forward symbol: {symbol} ===")
        try:
            result = run_symbol_walk_forward(live_root=live_root, symbol=symbol, args=args)
            results.append(result)
            print(
                f"{symbol}: status={result.get('status')} "
                f"best={result.get('best_candidate_id', '')} "
                f"test_score={result.get('best_test_score', 0.0)} "
                f"test_hit={result.get('best_test_objective_hit', False)} "
                f"label={result.get('best_overfit_label', '')}"
            )
        except Exception as exc:
            error = {
                "symbol": symbol,
                "status": "error",
                "error_type": exc.__class__.__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
            results.append(error)
            errors.append(error)
            print(f"{symbol}: ERROR {exc.__class__.__name__}: {exc}")
            if not args.continue_on_error:
                break

    payload = build_walk_forward_payload(
        walk_forward_run_id=run_id,
        symbols=symbols,
        settings=settings,
        symbol_results=results,
    )
    artifacts = write_walk_forward_artifacts(payload, out_dir)

    print("AI Auto Lab walk-forward universe run complete.")
    print(f"walk_forward_run_id: {run_id}")
    print(f"symbols_requested: {len(symbols)}")
    print(f"symbols_completed: {sum(1 for r in results if r.get('status') == 'ok')}")
    print(f"errors: {len(errors)}")
    for key, value in artifacts.items():
        print(f"{key}: {value}")

    return 1 if errors and not args.continue_on_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
