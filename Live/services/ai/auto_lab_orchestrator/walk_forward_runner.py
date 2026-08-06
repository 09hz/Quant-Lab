from __future__ import annotations

from pathlib import Path
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
import argparse
import hashlib
import json
import math
import statistics
import sys
import traceback


WALK_FORWARD_CACHE_CONTRACT = "authoritative_universe_packet_v2"


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


def resolve_universe_candidate_packet(
    live_root: Path,
    explicit_path: str = "",
    *,
    disabled: bool = False,
) -> Path | None:
    if disabled:
        return None
    if explicit_path:
        path = Path(explicit_path).expanduser().resolve()
        if not path.is_file():
            raise ValueError(f"Universe candidate packet does not exist: {path}")
        return path
    from services.ai.auto_lab_orchestrator.ui_report_loader import latest_dir

    run_dir = latest_dir(live_root / "data" / "auto_lab_universe_runs", "universe_results.json")
    return run_dir / "universe_results.json" if run_dir else None


def load_universe_candidate_packet(
    packet_path: str | Path,
    *,
    symbol: str,
    max_candidates: int,
) -> tuple[list, dict]:
    from services.ai.auto_lab_orchestrator.models import StrategyCandidate

    path = Path(packet_path).resolve()
    payload = json.loads(path.read_text(encoding="utf-8"))
    symbol_result = next(
        (
            row
            for row in payload.get("symbol_results", [])
            if str(row.get("symbol") or "").upper() == str(symbol).upper()
        ),
        None,
    )
    if not symbol_result:
        return [], {
            "packet_path": str(path),
            "universe_run_id": str(payload.get("universe_run_id") or ""),
            "status": "symbol_missing",
        }

    ranked_rows = [row for row in symbol_result.get("ranked_mutations", []) if isinstance(row, dict)]
    candidate_payloads = {
        str(row.get("candidate_id") or ""): row
        for row in ranked_rows
        if row.get("candidate_id") and row.get("script")
    }
    if not candidate_payloads:
        trace_path = Path(str(symbol_result.get("run_dir") or "")) / "strategy_build_trace.json"
        if trace_path.is_file():
            trace_payload = json.loads(trace_path.read_text(encoding="utf-8"))
            candidate_payloads = {
                str(row.get("candidate_id") or ""): {
                    "candidate_id": row.get("candidate_id"),
                    "name": row.get("candidate_name"),
                    "family": row.get("parent_id") or row.get("candidate_id"),
                    "script": row.get("final_code"),
                    "source": row.get("source") or "universe_strategy_trace",
                    "notes": row.get("next_test_idea") or "",
                }
                for row in trace_payload.get("traces", [])
                if isinstance(row, dict) and row.get("candidate_id") and row.get("final_code")
            }
    if not candidate_payloads:
        run_json = str((symbol_result.get("artifacts") or {}).get("run_json") or "")
        run_path = Path(run_json) if run_json else None
        if run_path and run_path.is_file():
            run_payload = json.loads(run_path.read_text(encoding="utf-8"))
            candidate_payloads = {
                str(row.get("candidate_id") or ""): row
                for row in run_payload.get("candidates", [])
                if isinstance(row, dict) and row.get("candidate_id") and row.get("script")
            }

    ordered_ids = [str(row.get("candidate_id") or "") for row in ranked_rows]
    candidates = []
    for candidate_id in ordered_ids:
        data = candidate_payloads.get(candidate_id)
        if not data:
            continue
        candidates.append(
            StrategyCandidate(
                candidate_id=candidate_id,
                name=str(data.get("name") or candidate_id),
                family=str(data.get("family") or data.get("strategy_family") or "universe_candidate"),
                script=str(data.get("script") or ""),
                parameters=dict(data.get("parameters") or {}),
                symbols=[str(symbol).upper()],
                tags=list(dict.fromkeys([*(data.get("tags") or []), "universe-packet", "walk-forward-input"])),
                source=f"universe_packet:{payload.get('universe_run_id', path.parent.name)}",
                notes=str(data.get("notes") or "Candidate loaded from an immutable Universe result packet."),
            )
        )
        if len(candidates) >= max(1, int(max_candidates or 1)):
            break
    return candidates, {
        "packet_path": str(path),
        "universe_run_id": str(payload.get("universe_run_id") or path.parent.name),
        "generated_at": str(payload.get("generated_at") or ""),
        "status": "ok" if candidates else "no_candidates",
        "candidate_count": len(candidates),
    }


def validate_walk_forward_dates(*, train_start: str, train_end: str, test_start: str, test_end: str) -> dict[str, str]:
    """Validate strictly chronological train and unseen-test boundaries."""
    values = {
        "train_start": train_start,
        "train_end": train_end,
        "test_start": test_start,
        "test_end": test_end,
    }
    parsed = {}
    for name, value in values.items():
        try:
            parsed[name] = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00")).date()
        except Exception as exc:
            raise ValueError(f"Invalid {name.replace('_', ' ')} date: {value!r}.") from exc
    if parsed["train_start"] > parsed["train_end"]:
        raise ValueError("Training start must be on or before training end.")
    if parsed["test_start"] > parsed["test_end"]:
        raise ValueError("Test start must be on or before test end.")
    if parsed["train_end"] >= parsed["test_start"]:
        raise ValueError(
            "Training and unseen-test windows overlap. Training end must be before test start."
        )
    return {name: value.isoformat() for name, value in parsed.items()}


def _run_id() -> str:
    from services.ai.auto_lab_orchestrator.models import local_run_timestamp

    return "walk_forward_" + local_run_timestamp()


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


def _window_date(bars, index: int) -> str:
    try:
        if hasattr(bars, "columns"):
            for column in ("date", "datetime", "timestamp", "time"):
                if column in bars.columns:
                    value = bars.iloc[index][column]
                    return value.isoformat() if hasattr(value, "isoformat") else str(value)
        row = bars[index]
        if isinstance(row, dict):
            value = next((row.get(key) for key in ("date", "datetime", "timestamp", "time") if row.get(key) is not None), "")
        else:
            value = next((getattr(row, key) for key in ("date", "datetime", "timestamp", "time") if getattr(row, key, None) is not None), "")
        return value.isoformat() if hasattr(value, "isoformat") else str(value)
    except Exception:
        return ""


def _slice_bars(bars, start: int, end: int):
    if hasattr(bars, "iloc"):
        return bars.iloc[start:end].reset_index(drop=True)
    return bars[start:end]


def reserve_final_holdout(bars, *, holdout_pct: float = 20.0, min_holdout_bars: int = 20) -> dict:
    """Reserve the final chronological bars without exposing them to validation."""
    total_rows = len(bars) if bars is not None else 0
    minimum = max(1, int(min_holdout_bars or 1))
    percentage = min(100.0, max(0.0, _safe_float(holdout_pct, 20.0)))
    holdout_rows = max(minimum, int(math.ceil(total_rows * percentage / 100.0)))

    if total_rows <= holdout_rows:
        return {
            "holdout_available": False,
            "validation_start": _window_date(bars, 0) if total_rows else "",
            "validation_end": _window_date(bars, total_rows - 1) if total_rows else "",
            "holdout_start": "",
            "holdout_end": "",
            "holdout_rows": 0,
            "validation_bars": _slice_bars(bars, 0, total_rows) if bars is not None else [],
            "holdout_bars": _slice_bars(bars, 0, 0) if bars is not None else [],
        }

    split_index = total_rows - holdout_rows
    return {
        "holdout_available": True,
        "validation_start": _window_date(bars, 0),
        "validation_end": _window_date(bars, split_index - 1),
        "holdout_start": _window_date(bars, split_index),
        "holdout_end": _window_date(bars, total_rows - 1),
        "holdout_rows": holdout_rows,
        "validation_bars": _slice_bars(bars, 0, split_index),
        "holdout_bars": _slice_bars(bars, split_index, total_rows),
    }


def classify_holdout_regime(bars) -> str:
    """Classify holdout-only price trend and bar-return volatility."""
    try:
        if hasattr(bars, "columns") and "close" in bars.columns:
            closes = [_safe_float(value, 0.0) for value in bars["close"].dropna().tolist()]
        else:
            closes = []
            for row in ([] if bars is None else bars):
                value = row.get("close") if isinstance(row, dict) else getattr(row, "close", 0.0)
                closes.append(_safe_float(value, 0.0))
        closes = [value for value in closes if value > 0]
    except Exception:
        closes = []

    if len(closes) < 2:
        return "unavailable"

    total_return_pct = ((closes[-1] / closes[0]) - 1.0) * 100.0
    returns_pct = [((current / previous) - 1.0) * 100.0 for previous, current in zip(closes, closes[1:])]
    volatility_pct = statistics.pstdev(returns_pct) if len(returns_pct) > 1 else 0.0

    if total_return_pct > 2.0:
        trend = "uptrend"
    elif total_return_pct < -2.0:
        trend = "downtrend"
    else:
        trend = "sideways"
    volatility = "high_volatility" if volatility_pct >= 2.0 else "low_volatility"
    return f"{trend}_{volatility}"


def build_rolling_windows(bars, *, window_count: int = 3, min_bars: int = 20) -> list[dict]:
    """Partition unseen bars into chronological, non-overlapping validation windows."""
    total_rows = len(bars) if bars is not None else 0
    requested_count = max(1, int(window_count or 1))
    minimum = max(2, int(min_bars or 2))
    available_count = total_rows // minimum
    actual_count = min(requested_count, available_count)
    if actual_count < 1:
        return []

    windows = []
    for index in range(actual_count):
        start_index = (index * total_rows) // actual_count
        end_index = ((index + 1) * total_rows) // actual_count
        if hasattr(bars, "iloc"):
            window_bars = bars.iloc[start_index:end_index].reset_index(drop=True)
        else:
            window_bars = bars[start_index:end_index]
        windows.append(
            {
                "window": index + 1,
                "start": _window_date(bars, start_index),
                "end": _window_date(bars, end_index - 1),
                "row_count": len(window_bars),
                "bars": window_bars,
            }
        )
    return windows


def summarize_rolling_results(rows: list[dict], *, max_drawdown_pct: float) -> dict:
    if not rows:
        return {
            "rolling_status": "unavailable",
            "rolling_window_count": 0,
            "rolling_engine_pass_count": 0,
            "rolling_pass_count": 0,
            "rolling_pass_rate_pct": 0.0,
            "rolling_median_score": 0.0,
            "rolling_worst_score": 0.0,
            "rolling_worst_drawdown_pct": 0.0,
            "rolling_total_fees": 0.0,
            "rolling_total_slippage": 0.0,
        }

    drawdown_limit = abs(_safe_float(max_drawdown_pct, 0.0))
    passes = [
        row
        for row in rows
        if bool(row.get("engine_pass"))
        and bool(row.get("research_pass"))
        and abs(_safe_float(row.get("max_drawdown_pct"), 0.0)) <= drawdown_limit
    ]
    pass_rate = (len(passes) / len(rows)) * 100.0
    if len(passes) * 3 >= len(rows) * 2:
        status = "robust"
    elif passes:
        status = "partial"
    else:
        status = "failed"

    scores = [_safe_float(row.get("score"), 0.0) for row in rows]
    drawdowns = [abs(_safe_float(row.get("max_drawdown_pct"), 0.0)) for row in rows]
    return {
        "rolling_status": status,
        "rolling_window_count": len(rows),
        "rolling_engine_pass_count": sum(1 for row in rows if row.get("engine_pass")),
        "rolling_pass_count": len(passes),
        "rolling_pass_rate_pct": round(pass_rate, 4),
        "rolling_median_score": round(statistics.median(scores), 4),
        "rolling_worst_score": round(min(scores), 4),
        "rolling_worst_drawdown_pct": round(max(drawdowns), 4),
        "rolling_total_fees": round(sum(_safe_float(row.get("fees"), 0.0) for row in rows), 4),
        "rolling_total_slippage": round(sum(_safe_float(row.get("slippage"), 0.0) for row in rows), 4),
    }


def run_rolling_stress_test(
    *,
    adapter,
    candidate,
    symbol: str,
    test_bars,
    timeframe: str,
    initial_cash: float,
    target_equity: float,
    max_drawdown_pct: float,
    window_count: int,
    min_bars: int,
    commission_per_order: float,
    slippage_bps: float,
) -> dict:
    from services.ai.auto_lab_orchestrator.models import ExperimentGoal
    from services.ai.auto_lab_orchestrator.scorecard import score_strategy_result

    public_rows = []
    for window in build_rolling_windows(test_bars, window_count=window_count, min_bars=min_bars):
        goal = ExperimentGoal(
            question=f"Test 3 rolling stress validation for {symbol}, window {window['window']}.",
            symbols=[symbol],
            timeframe=timeframe,
            starting_cash=initial_cash,
            target_equity=target_equity,
            max_drawdown_pct=max_drawdown_pct,
            min_trades=1,
            execution_mode="next_open",
            commission_per_order=max(0.0, _safe_float(commission_per_order, 0.0)),
            slippage_bps=max(0.0, _safe_float(slippage_bps, 0.0)),
            max_runs=1,
            simulation_only=True,
            notes="Fixed-candidate rolling out-of-sample validation with fee and slippage stress.",
        )
        result = adapter.run_candidate(candidate, window["bars"], goal, symbol)
        scorecard = score_strategy_result(result, goal)
        metrics = dict(getattr(result, "metrics", {}) or {})
        public_rows.append(
            {
                "window": window["window"],
                "start": window["start"],
                "end": window["end"],
                "row_count": window["row_count"],
                "score": scorecard.total_score,
                "grade": scorecard.grade,
                "engine_pass": scorecard.engine_pass,
                "research_pass": scorecard.research_pass,
                "objective_hit": scorecard.objective_hit,
                "objective_progress_pct": scorecard.objective_progress_pct,
                "total_return_pct": metrics.get("total_return_pct", 0.0),
                "final_equity": metrics.get("final_equity", 0.0),
                "max_drawdown_pct": metrics.get("max_drawdown_pct", 0.0),
                "trade_count": metrics.get("trade_count", 0),
                "fees": metrics.get("fees", 0.0),
                "slippage": metrics.get("slippage", 0.0),
                "buy_hold_return_pct": buy_hold_return_pct(window["bars"]),
                "warnings": list(scorecard.warnings or []),
                "fail_reasons": list(scorecard.fail_reasons or []),
                "engine_errors": list(getattr(result, "errors", []) or []),
                "engine_warnings": list(getattr(result, "warnings", []) or []),
            }
        )

    summary = summarize_rolling_results(public_rows, max_drawdown_pct=max_drawdown_pct)
    summary.update(
        {
            "rolling_commission_per_order": max(0.0, _safe_float(commission_per_order, 0.0)),
            "rolling_slippage_bps": max(0.0, _safe_float(slippage_bps, 0.0)),
            "rolling_windows": public_rows,
        }
    )
    return summary


def _empty_holdout_result() -> dict:
    return {
        "holdout_available": False,
        "holdout_start": "",
        "holdout_end": "",
        "holdout_rows": 0,
        "holdout_score": 0.0,
        "holdout_engine_pass": False,
        "holdout_research_pass": False,
        "holdout_objective_hit": False,
        "holdout_objective_progress_pct": 0.0,
        "holdout_total_return_pct": 0.0,
        "holdout_max_drawdown_pct": 0.0,
        "holdout_trade_count": 0,
        "holdout_fees": 0.0,
        "holdout_slippage": 0.0,
        "holdout_regime": "unavailable",
        "holdout_errors": [],
        "holdout_warnings": [],
    }


def best_holdout_symbol_fields(row: dict | None) -> dict:
    source = row or {}
    return {
        f"best_{key}": source.get(key, default)
        for key, default in _empty_holdout_result().items()
    }


def run_final_holdout_test(
    *,
    adapter,
    candidate,
    symbol: str,
    holdout_bars,
    holdout_available: bool,
    timeframe: str,
    initial_cash: float,
    target_equity: float,
    max_drawdown_pct: float,
    commission_per_order: float,
    slippage_bps: float,
) -> dict:
    """Run a fixed candidate once on the untouched final holdout."""
    if not holdout_available or holdout_bars is None or len(holdout_bars) < 1:
        return _empty_holdout_result()

    from services.ai.auto_lab_orchestrator.models import ExperimentGoal
    from services.ai.auto_lab_orchestrator.scorecard import score_strategy_result

    goal = ExperimentGoal(
        question=f"Test 4 final untouched holdout for {symbol}.",
        symbols=[symbol],
        timeframe=timeframe,
        starting_cash=initial_cash,
        target_equity=target_equity,
        max_drawdown_pct=max_drawdown_pct,
        min_trades=1,
        execution_mode="next_open",
        commission_per_order=max(0.0, _safe_float(commission_per_order, 0.0)),
        slippage_bps=max(0.0, _safe_float(slippage_bps, 0.0)),
        max_runs=1,
        simulation_only=True,
        notes="Fixed-candidate final holdout with fee and slippage stress; no reselection or resizing.",
    )
    result = adapter.run_candidate(candidate, holdout_bars, goal, symbol)
    scorecard = score_strategy_result(result, goal)
    metrics = dict(getattr(result, "metrics", {}) or {})
    return {
        "holdout_available": True,
        "holdout_start": _window_date(holdout_bars, 0),
        "holdout_end": _window_date(holdout_bars, len(holdout_bars) - 1),
        "holdout_rows": len(holdout_bars),
        "holdout_score": scorecard.total_score,
        "holdout_engine_pass": scorecard.engine_pass,
        "holdout_research_pass": scorecard.research_pass,
        "holdout_objective_hit": scorecard.objective_hit,
        "holdout_objective_progress_pct": scorecard.objective_progress_pct,
        "holdout_total_return_pct": metrics.get("total_return_pct", 0.0),
        "holdout_max_drawdown_pct": metrics.get("max_drawdown_pct", 0.0),
        "holdout_trade_count": metrics.get("trade_count", 0),
        "holdout_fees": metrics.get("fees", 0.0),
        "holdout_slippage": metrics.get("slippage", 0.0),
        "holdout_regime": classify_holdout_regime(holdout_bars),
        "holdout_errors": list(getattr(result, "errors", []) or []),
        "holdout_warnings": list(getattr(result, "warnings", []) or []),
    }


def _result_by_key(run):
    return {(r.candidate_id, r.symbol): r for r in run.results}


def _candidate_by_id(candidates):
    return {c.candidate_id: c for c in candidates}


def _signal_fingerprint(result) -> tuple | None:
    raw = dict(getattr(result, "raw_summary", {}) or {})
    strategy_result = raw.get("strategy_result")
    if not isinstance(strategy_result, dict):
        return None
    signals = strategy_result.get("signals")
    if not isinstance(signals, list):
        return None
    return tuple(
        (
            int(signal.get("index", -1)),
            str(signal.get("side") or signal.get("action") or "").upper(),
        )
        for signal in signals
        if isinstance(signal, dict)
    )


def select_diverse_scorecards(*, scorecards, candidates_by_id: dict, results, limit: int):
    """Select high scores while excluding train-equivalent signal behavior."""
    ordered = sorted(scorecards, key=lambda scorecard: scorecard.total_score, reverse=True)
    results_by_id = {result.candidate_id: result for result in results}
    selected = []
    selected_ids: set[str] = set()
    seen_fingerprints: set[tuple] = set()
    family_counts: dict[str, int] = {}

    for enforce_family_quota in (True, False):
        for scorecard in ordered:
            if len(selected) >= max(0, int(limit)):
                return selected
            if scorecard.candidate_id in selected_ids:
                continue
            candidate = candidates_by_id.get(scorecard.candidate_id)
            if candidate is None:
                continue
            family = str(getattr(candidate, "family", "unknown") or "unknown")
            if enforce_family_quota and family_counts.get(family, 0) >= 1:
                continue
            fingerprint = _signal_fingerprint(results_by_id.get(scorecard.candidate_id))
            if fingerprint is not None and fingerprint in seen_fingerprints:
                continue
            selected.append(scorecard)
            selected_ids.add(scorecard.candidate_id)
            family_counts[family] = family_counts.get(family, 0) + 1
            if fingerprint is not None:
                seen_fingerprints.add(fingerprint)
    return selected


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


def _run_symbol_walk_forward_uncached(*, live_root: Path, symbol: str, args, progress_callback=None) -> dict:
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

    _report_symbol_progress(progress_callback, 4, "data", f"Loading train and test bars for {symbol}")
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
    full_test_bars, test_profile = load_csv_bars(
        csv_path=boot.csv_path,
        symbol=symbol,
        start=args.test_start,
        end=args.test_end,
    )
    holdout_split = reserve_final_holdout(
        full_test_bars,
        holdout_pct=getattr(args, "holdout_pct", 20.0),
        min_holdout_bars=getattr(args, "holdout_min_bars", 20),
    )
    test_bars = holdout_split["validation_bars"]
    holdout_bars = holdout_split["holdout_bars"]

    _report_symbol_progress(progress_callback, 12, "test_1", f"Preparing training candidates for {symbol}")

    train_buy_hold = buy_hold_return_pct(train_bars)
    test_buy_hold = buy_hold_return_pct(test_bars)

    packet_candidates = []
    packet_lineage = {
        "packet_path": str(getattr(args, "candidate_packet", "") or ""),
        "universe_run_id": "",
        "status": "not_configured",
        "candidate_count": 0,
    }
    if getattr(args, "candidate_packet", ""):
        packet_candidates, packet_lineage = load_universe_candidate_packet(
            args.candidate_packet,
            symbol=symbol,
            max_candidates=args.max_total_runs_per_symbol,
        )
        if not packet_candidates:
            raise ValueError(
                f"Universe candidate packet has no usable candidates for {symbol}: "
                f"{args.candidate_packet}"
            )
        seeds = packet_candidates
        candidate_source = "universe_packet"
    else:
        seeds = discover_strategy_seed_candidates(
            live_root=live_root,
            symbol=symbol,
            max_examples=args.max_examples,
            include_built_ins=True,
        )
        candidate_source = "seed_library_fallback"

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

    adapter = CoreStrategyBacktestAdapter()
    orchestrator = AutoLabOrchestrator(adapter=adapter, live_root=live_root)

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
    _report_symbol_progress(progress_callback, 20, "test_1", f"Running training baseline for {symbol}")
    baseline_run = orchestrator.run_experiment(
        goal=baseline_goal,
        candidates=sized_seeds_train,
        bars_by_symbol={symbol: train_bars},
        write_artifacts=False,
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
    if eligible_parents and packet_candidates:
        mutations = eligible_parents[: args.max_total_runs_per_symbol]
    elif eligible_parents:
        mutations = generate_mutations_for_parents(
            parents=eligible_parents,
            max_mutations_per_parent=args.max_mutations_per_parent,
            max_total=args.max_total_runs_per_symbol,
            mutate_quantity=args.mutate_quantity,
        )

    _report_symbol_progress(progress_callback, 36, "test_1", f"Generated training mutations for {symbol}")

    if not mutations:
        return {
            "symbol": symbol,
            "status": "no_train_mutations",
            "data_source": boot.source,
            "csv_path": boot.csv_path,
            "train_rows": train_profile.row_count,
            "full_test_rows": test_profile.row_count,
            "test_rows": len(test_bars),
            "reserved_holdout_rows": holdout_split["holdout_rows"],
            "buy_hold_train_return_pct": train_buy_hold,
            "buy_hold_test_return_pct": test_buy_hold,
            "validated_candidates": [],
            "candidate_source": candidate_source,
            "candidate_packet": packet_lineage,
            **best_holdout_symbol_fields(None),
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
    _report_symbol_progress(progress_callback, 42, "test_1", f"Ranking training mutations for {symbol}")
    train_run = orchestrator.run_experiment(
        goal=train_goal,
        candidates=sized_mutations_train,
        bars_by_symbol={symbol: train_bars},
        write_artifacts=False,
    )
    train_run.summary["walk_forward_phase"] = "train_mutation"
    train_run.summary["data_profile"] = train_profile.to_dict()
    train_run.summary["sizing"] = train_mutation_sizing
    normalize_run_execution_quality(train_run, context=f"{symbol}_train_mutation")
    write_run_bundle(train_run, Path(train_run.artifacts["report_md"]).parent)

    train_candidates_by_id = _candidate_by_id(sized_mutations_train)
    train_scorecards_sorted = sorted(train_run.scorecards, key=lambda sc: sc.total_score, reverse=True)
    preferred = [sc for sc in train_scorecards_sorted if sc.engine_pass and sc.research_pass]
    train_selected = select_diverse_scorecards(
        scorecards=preferred,
        candidates_by_id=train_candidates_by_id,
        results=train_run.results,
        limit=args.top_n_per_symbol,
    )
    if len(train_selected) < args.top_n_per_symbol:
        extra = [sc for sc in train_scorecards_sorted if sc.engine_pass]
        expanded = select_diverse_scorecards(
            scorecards=[*train_selected, *extra],
            candidates_by_id=train_candidates_by_id,
            results=train_run.results,
            limit=args.top_n_per_symbol,
        )
        train_selected = expanded

    selected_candidates = [train_candidates_by_id[sc.candidate_id] for sc in train_selected if sc.candidate_id in train_candidates_by_id]
    if not selected_candidates:
        return {
            "symbol": symbol,
            "status": "no_train_selected",
            "data_source": boot.source,
            "csv_path": boot.csv_path,
            "train_rows": train_profile.row_count,
            "full_test_rows": test_profile.row_count,
            "test_rows": len(test_bars),
            "reserved_holdout_rows": holdout_split["holdout_rows"],
            "buy_hold_train_return_pct": train_buy_hold,
            "buy_hold_test_return_pct": test_buy_hold,
            "validated_candidates": [],
            "candidate_source": candidate_source,
            "candidate_packet": packet_lineage,
            **best_holdout_symbol_fields(None),
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
    _report_symbol_progress(progress_callback, 58, "test_2", f"Testing selected strategies on unseen {symbol} data")
    test_run = orchestrator.run_experiment(
        goal=test_goal,
        candidates=sized_test_candidates,
        bars_by_symbol={symbol: test_bars},
        write_artifacts=False,
    )
    test_run.summary["walk_forward_phase"] = "test_validation"
    test_run.summary["data_profile"] = {
        **test_profile.to_dict(),
        "row_count": len(test_bars),
        "first_date": holdout_split["validation_start"],
        "last_date": holdout_split["validation_end"],
        "reserved_holdout_rows": holdout_split["holdout_rows"],
    }
    test_run.summary["sizing"] = test_sizing
    normalize_run_execution_quality(test_run, context=f"{symbol}_test_validation")
    write_run_bundle(test_run, Path(test_run.artifacts["report_md"]).parent)

    train_sc_by_id = {sc.candidate_id: sc for sc in train_run.scorecards}
    test_result_by_key = _result_by_key(test_run)
    test_candidate_by_id = _candidate_by_id(sized_test_candidates)

    rows = []
    sorted_test_scorecards = sorted(test_run.scorecards, key=lambda sc: sc.total_score, reverse=True)
    validation_count = max(1, len(sorted_test_scorecards))
    for validation_index, test_sc in enumerate(sorted_test_scorecards):
        train_sc = train_sc_by_id.get(test_sc.candidate_id)
        candidate = test_candidate_by_id.get(test_sc.candidate_id)
        test_result = test_result_by_key.get((test_sc.candidate_id, test_sc.symbol))
        if train_sc and candidate:
            row = _row_from_train_test(symbol, train_sc, test_sc, test_result, candidate, test_buy_hold)
            validation_start = 68.0 + (validation_index * 23.0 / validation_count)
            _report_symbol_progress(
                progress_callback,
                validation_start,
                "test_3",
                f"Rolling stress test {validation_index + 1}/{validation_count} for {symbol}",
            )
            row.update(
                run_rolling_stress_test(
                    adapter=adapter,
                    candidate=candidate,
                    symbol=symbol,
                    test_bars=test_bars,
                    timeframe=args.timeframe,
                    initial_cash=initial_cash,
                    target_equity=target_equity,
                    max_drawdown_pct=args.max_drawdown_pct,
                    window_count=args.rolling_windows,
                    min_bars=args.rolling_min_bars,
                    commission_per_order=args.rolling_commission_per_order,
                    slippage_bps=args.rolling_slippage_bps,
                )
            )
            _report_symbol_progress(
                progress_callback,
                validation_start + (13.0 / validation_count),
                "test_4",
                f"Final holdout test {validation_index + 1}/{validation_count} for {symbol}",
            )
            row.update(
                run_final_holdout_test(
                    adapter=adapter,
                    candidate=candidate,
                    symbol=symbol,
                    holdout_bars=holdout_bars,
                    holdout_available=holdout_split["holdout_available"],
                    timeframe=args.timeframe,
                    initial_cash=initial_cash,
                    target_equity=target_equity,
                    max_drawdown_pct=args.max_drawdown_pct,
                    commission_per_order=args.rolling_commission_per_order,
                    slippage_bps=args.rolling_slippage_bps,
                )
            )
            rows.append(row)

    best = rows[0] if rows else {}

    _report_symbol_progress(progress_callback, 96, "artifacts", f"Preparing walk-forward results for {symbol}")

    return {
        "symbol": symbol,
        "status": "ok",
        "data_source": boot.source,
        "csv_path": boot.csv_path,
        "train_rows": train_profile.row_count,
        "full_test_rows": test_profile.row_count,
        "test_rows": len(test_bars),
        "reserved_holdout_rows": holdout_split["holdout_rows"],
        "train_first_date": train_profile.first_date,
        "train_last_date": train_profile.last_date,
        "test_first_date": holdout_split["validation_start"],
        "test_last_date": holdout_split["validation_end"],
        "buy_hold_train_return_pct": train_buy_hold,
        "buy_hold_test_return_pct": test_buy_hold,
        "baseline_run_id": baseline_run.run_id,
        "train_run_id": train_run.run_id,
        "test_run_id": test_run.run_id,
        "train_run_dir": str(Path(train_run.artifacts["report_md"]).parent),
        "test_run_dir": str(Path(test_run.artifacts["report_md"]).parent),
        "train_research_pass_candidates": sum(1 for sc in train_run.scorecards if sc.research_pass),
        "candidate_source": candidate_source,
        "candidate_packet": packet_lineage,
        "validated_candidates": rows,
        "best_candidate_id": best.get("candidate_id", ""),
        "best_train_score": best.get("train_score", 0.0),
        "best_test_score": best.get("test_score", 0.0),
        "best_train_objective_hit": best.get("train_objective_hit", False),
        "best_test_objective_hit": best.get("test_objective_hit", False),
        "best_test_objective_progress_pct": best.get("test_objective_progress_pct", 0.0),
        "best_overfit_label": best.get("overfit_label", ""),
        "best_rolling_status": best.get("rolling_status", "unavailable"),
        "best_rolling_pass_rate_pct": best.get("rolling_pass_rate_pct", 0.0),
        "best_rolling_worst_score": best.get("rolling_worst_score", 0.0),
        **best_holdout_symbol_fields(best),
    }


def run_symbol_walk_forward(*, live_root: Path, symbol: str, args, progress_callback=None) -> dict:
    from services.ai.auto_lab_orchestrator.bars_bootstrapper import bootstrap_bars_csv
    from services.ai.auto_lab_orchestrator.orchestrator import (
        build_exact_result_cache_key,
        load_exact_symbol_result,
        save_exact_symbol_result,
    )

    boot = bootstrap_bars_csv(
        live_root=live_root,
        symbol=symbol,
        start=args.train_start,
        end=args.test_end,
        timeframe=args.timeframe,
        prefer_local=not args.yfinance_first,
        allow_yfinance=not args.local_only,
    )
    settings = {
        key: value
        for key, value in vars(args).items()
        if key not in {"run_id", "continue_on_error", "workers", "no_cache"}
    }
    settings["cache_contract"] = WALK_FORWARD_CACHE_CONTRACT
    packet_path = Path(str(getattr(args, "candidate_packet", "") or ""))
    settings["candidate_packet_sha256"] = (
        hashlib.sha256(packet_path.read_bytes()).hexdigest() if packet_path.is_file() else ""
    )
    cache_key = build_exact_result_cache_key(
        live_root=live_root,
        kind="walk_forward",
        symbol=symbol,
        csv_path=Path(boot.csv_path),
        settings=settings,
    )
    cached = None if getattr(args, "no_cache", False) else load_exact_symbol_result(live_root=live_root, kind="walk_forward", cache_key=cache_key)
    if cached is not None and getattr(args, "candidate_packet", ""):
        if cached.get("candidate_source") != "universe_packet":
            cached = None
    if cached is not None:
        cached["cache_hit"] = True
        cached["cache_key"] = cache_key
        _report_symbol_progress(progress_callback, 96, "cache_hit", f"Loaded exact cached result for {symbol}")
        return cached
    result = _run_symbol_walk_forward_uncached(
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
            kind="walk_forward",
            cache_key=cache_key,
            result=result,
        )
    return result


def _run_walk_forward_symbol_worker(live_root_text: str, symbol: str, args_dict: dict) -> dict:
    return run_symbol_walk_forward(
        live_root=Path(live_root_text),
        symbol=symbol,
        args=argparse.Namespace(**args_dict),
        progress_callback=None,
    )


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run multi-symbol walk-forward validation.")
    parser.add_argument("--symbols", default="AMD,NVDA,MSFT,AAPL,TSLA")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--candidate-packet", default="", help="Exact Universe results JSON used as candidate lineage.")
    parser.add_argument("--no-universe-packet", action="store_true", help="Use the seed library instead of a Universe packet.")
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
    parser.add_argument("--initial-cash", default=12000.0)
    parser.add_argument("--target-equity", default=24000.0)
    parser.add_argument("--max-drawdown-pct", type=float, default=30.0)
    parser.add_argument("--max-examples", type=int, default=8)
    parser.add_argument("--max-mutations-per-parent", type=int, default=4)
    parser.add_argument("--max-total-runs-per-symbol", type=int, default=20)
    parser.add_argument("--top-n-per-symbol", type=int, default=3)
    parser.add_argument("--rolling-windows", type=int, default=3)
    parser.add_argument("--rolling-min-bars", type=int, default=20)
    parser.add_argument("--rolling-commission-per-order", type=float, default=1.0)
    parser.add_argument("--rolling-slippage-bps", type=float, default=5.0)
    parser.add_argument("--holdout-pct", type=float, default=20.0)
    parser.add_argument("--holdout-min-bars", type=int, default=20)
    parser.add_argument("--mutate-quantity", action="store_true")
    parser.add_argument("--strict-parent-gate", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--no-cache", action="store_true")
    return parser


def main() -> int:
    live_root = _bootstrap_import_path()
    args = build_argument_parser().parse_args()

    from services.ai.auto_lab_orchestrator.capital_controls import normalize_capital_with_warnings
    from services.ai.auto_lab_orchestrator.walk_forward_reporter import build_walk_forward_payload, write_walk_forward_artifacts

    capital, capital_warnings = normalize_capital_with_warnings(
        initial_cash=args.initial_cash,
        target_cash=args.target_equity,
        cash_exposure_pct=args.cash_exposure_pct,
        sizing_mode=args.sizing_mode,
    )
    args.initial_cash = capital.initial_cash
    args.target_equity = capital.target_cash
    args.cash_exposure_pct = capital.cash_exposure_pct
    for warning in capital_warnings:
        print(f"[CAPITAL ASSUMPTION] {warning}")

    symbols = _parse_symbols(args.symbols)
    if not symbols:
        print("No symbols provided.")
        return 2

    try:
        validated_dates = validate_walk_forward_dates(
            train_start=args.train_start,
            train_end=args.train_end,
            test_start=args.test_start,
            test_end=args.test_end,
        )
    except ValueError as exc:
        print(f"Invalid walk-forward date configuration: {exc}")
        return 2
    args.train_start = validated_dates["train_start"]
    args.train_end = validated_dates["train_end"]
    args.test_start = validated_dates["test_start"]
    args.test_end = validated_dates["test_end"]

    try:
        candidate_packet = resolve_universe_candidate_packet(
            live_root,
            args.candidate_packet,
            disabled=args.no_universe_packet,
        )
    except ValueError as exc:
        print(f"Invalid Universe candidate packet: {exc}")
        return 2
    args.candidate_packet = str(candidate_packet) if candidate_packet else ""

    run_id = str(args.run_id or _run_id()).strip()
    if not run_id.replace("-", "").replace("_", "").isalnum():
        print("Invalid run ID. Use letters, numbers, underscores, or hyphens only.")
        return 2
    out_dir = live_root / "data" / "auto_lab_walk_forward_runs" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    settings = {
        "symbols": symbols,
        "validation_mode": "train_unseen_test_then_rolling_stress_then_final_holdout",
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
        "rolling_windows": args.rolling_windows,
        "rolling_min_bars": args.rolling_min_bars,
        "rolling_commission_per_order": args.rolling_commission_per_order,
        "rolling_slippage_bps": args.rolling_slippage_bps,
        "holdout_pct": args.holdout_pct,
        "holdout_min_bars": args.holdout_min_bars,
        "max_mutations_per_parent": args.max_mutations_per_parent,
        "max_total_runs_per_symbol": args.max_total_runs_per_symbol,
        "workers": min(max(1, int(args.workers or 1)), 4),
        "exact_result_cache": not args.no_cache,
        "candidate_source": "universe_packet" if args.candidate_packet else "seed_library_fallback",
        "candidate_packet": args.candidate_packet,
        "benchmark": "buy_and_hold_return_pct",
        "simulation_only": True,
    }

    results = []
    errors = []

    _emit_progress(2, "starting", f"Preparing walk-forward validation for {len(symbols)} symbols")
    worker_count = min(max(1, int(args.workers or 1)), 4, len(symbols))
    if worker_count > 1:
        from services.ai.auto_lab_orchestrator.bars_bootstrapper import bootstrap_bars_csv

        for symbol in symbols:
            bootstrap_bars_csv(
                live_root=live_root,
                symbol=symbol,
                start=args.train_start,
                end=args.test_end,
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
                    _run_walk_forward_symbol_worker,
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
                        **best_holdout_symbol_fields(None),
                    }
                    by_symbol[symbol] = error
                    errors.append(error)
                _emit_progress(
                    4.0 + (90.0 * completed_index / len(symbols)),
                    "symbol_complete",
                    f"Completed {completed_index}/{len(symbols)} walk-forward symbols",
                )
        results = [by_symbol[symbol] for symbol in symbols if symbol in by_symbol]
    else:
        for symbol_index, symbol in enumerate(symbols):
            symbol_span = 90.0 / max(1, len(symbols))
            symbol_start = 4.0 + (symbol_index * symbol_span)

            def report_symbol(percent, stage, message, *, _start=symbol_start):
                overall = _start + (symbol_span * max(0.0, min(100.0, float(percent))) / 100.0)
                _emit_progress(overall, stage, message)

            try:
                results.append(
                    run_symbol_walk_forward(live_root=live_root, symbol=symbol, args=args, progress_callback=report_symbol)
                )
            except Exception as exc:
                error = {"symbol": symbol, "status": "error", "error_type": exc.__class__.__name__, "error": str(exc), "traceback": traceback.format_exc(), **best_holdout_symbol_fields(None)}
                results.append(error)
                errors.append(error)
                if not args.continue_on_error:
                    break

    _emit_progress(96, "reports", "Building walk-forward leaderboard and promotion reports")
    payload = build_walk_forward_payload(
        walk_forward_run_id=run_id,
        symbols=symbols,
        settings=settings,
        symbol_results=results,
    )
    artifacts = write_walk_forward_artifacts(payload, out_dir)
    _emit_progress(99, "finalizing", "Finalizing walk-forward research artifacts")

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
