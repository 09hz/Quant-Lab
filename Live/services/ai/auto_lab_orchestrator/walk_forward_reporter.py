from __future__ import annotations

from pathlib import Path
from typing import Any
from datetime import datetime, timezone
import json
import math


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, str) and not value.strip():
            return default
        out = float(value)
        if math.isnan(out) or math.isinf(out):
            return default
        return out
    except Exception:
        return default


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.2f}"
    try:
        return f"{float(value):.2f}"
    except Exception:
        return str(value)


def overfit_label(train_progress: float, test_progress: float, train_hit: bool, test_hit: bool) -> str:
    train_progress = _safe_float(train_progress)
    test_progress = _safe_float(test_progress)

    if train_hit and test_hit:
        return "walk_forward_pass"
    if train_progress >= 75 and test_progress < 25:
        return "high_overfit_warning"
    if train_progress >= 50 and test_progress < 25:
        return "medium_overfit_warning"
    if test_progress >= train_progress * 0.5 and test_progress > 0:
        return "partial_survival"
    return "weak_out_of_sample"


def build_walk_forward_payload(
    *,
    walk_forward_run_id: str,
    symbols: list[str],
    settings: dict[str, Any],
    symbol_results: list[dict[str, Any]],
) -> dict[str, Any]:
    all_rows = []
    for symbol_result in symbol_results:
        for row in symbol_result.get("validated_candidates") or []:
            all_rows.append(row)

    ranked_validated = sorted(
        all_rows,
        key=lambda item: (
            bool(item.get("test_research_pass")),
            bool(item.get("test_objective_hit")),
            _safe_float(item.get("test_score"), 0.0),
            _safe_float(item.get("test_objective_progress_pct"), 0.0),
        ),
        reverse=True,
    )

    ranked_symbols = sorted(
        symbol_results,
        key=lambda item: (
            _safe_float(item.get("best_test_score"), 0.0),
            _safe_float(item.get("best_test_objective_progress_pct"), 0.0),
        ),
        reverse=True,
    )

    return {
        "schema_version": "walk_forward_universe_v21_6",
        "walk_forward_run_id": walk_forward_run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "symbols": symbols,
        "settings": settings,
        "symbol_results": symbol_results,
        "ranked_symbols": ranked_symbols,
        "ranked_validated_candidates": ranked_validated,
        "safety": {
            "simulation_only": True,
            "broker_calls": False,
            "live_orders": False,
            "note": "Walk-forward runner is research/simulation-only.",
        },
    }


def render_walk_forward_report(payload: dict[str, Any]) -> str:
    lines = [
        "# AI Auto Lab Walk-Forward Universe Report",
        "",
        "AI Auto Lab is research/simulation-only. It does not place orders, connect to brokers, or provide personalized financial advice.",
        "",
        "## Run",
        "",
        f"- walk_forward_run_id: `{payload.get('walk_forward_run_id')}`",
        f"- generated_at: `{payload.get('generated_at')}`",
        f"- symbols: {', '.join(payload.get('symbols') or [])}",
        "",
        "## Settings",
        "",
    ]
    for key, value in (payload.get("settings") or {}).items():
        lines.append(f"- {key}: {value}")

    lines += [
        "",
        "## Symbol walk-forward leaderboard",
        "",
        "| Rank | Symbol | Best candidate | Train score | Test score | Train hit | Test hit | Test progress | Buy-hold test | Overfit label |",
        "|---:|---|---|---:|---:|---|---|---:|---:|---|",
    ]

    for rank, row in enumerate(payload.get("ranked_symbols") or [], start=1):
        lines.append(
            f"| {rank} | {row.get('symbol')} | {row.get('best_candidate_id', '')} | "
            f"{_fmt(row.get('best_train_score', 0.0))} | {_fmt(row.get('best_test_score', 0.0))} | "
            f"{row.get('best_train_objective_hit', False)} | {row.get('best_test_objective_hit', False)} | "
            f"{_fmt(row.get('best_test_objective_progress_pct', 0.0))}% | "
            f"{_fmt(row.get('buy_hold_test_return_pct', 0.0))}% | "
            f"{row.get('best_overfit_label', '')} |"
        )

    lines += [
        "",
        "## Top validated candidates",
        "",
        "| Rank | Symbol | Candidate | Train score | Test score | Train progress | Test progress | Test hit | Buy-hold test | Overfit label |",
        "|---:|---|---|---:|---:|---:|---:|---|---:|---|",
    ]

    for rank, row in enumerate((payload.get("ranked_validated_candidates") or [])[:30], start=1):
        lines.append(
            f"| {rank} | {row.get('symbol')} | {row.get('candidate_id')} | "
            f"{_fmt(row.get('train_score', 0.0))} | {_fmt(row.get('test_score', 0.0))} | "
            f"{_fmt(row.get('train_objective_progress_pct', 0.0))}% | "
            f"{_fmt(row.get('test_objective_progress_pct', 0.0))}% | "
            f"{row.get('test_objective_hit', False)} | "
            f"{_fmt(row.get('buy_hold_test_return_pct', 0.0))}% | "
            f"{row.get('overfit_label', '')} |"
        )

    lines += [
        "",
        "## Symbol details",
        "",
    ]

    for symbol_result in payload.get("ranked_symbols") or []:
        lines += [
            f"### {symbol_result.get('symbol')}",
            "",
            f"- data_source: {symbol_result.get('data_source')}",
            f"- train_rows: {symbol_result.get('train_rows')}",
            f"- test_rows: {symbol_result.get('test_rows')}",
            f"- buy_hold_train_return_pct: {_fmt(symbol_result.get('buy_hold_train_return_pct', 0.0))}%",
            f"- buy_hold_test_return_pct: {_fmt(symbol_result.get('buy_hold_test_return_pct', 0.0))}%",
            f"- train_research_pass_candidates: {symbol_result.get('train_research_pass_candidates')}",
            f"- validated_candidate_count: {len(symbol_result.get('validated_candidates') or [])}",
            "",
            "| Rank | Candidate | Train score | Test score | Test return | Test drawdown | Test trades | Overfit label |",
            "|---:|---|---:|---:|---:|---:|---:|---|",
        ]
        for rank, row in enumerate(symbol_result.get("validated_candidates") or [], start=1):
            lines.append(
                f"| {rank} | {row.get('candidate_id')} | {_fmt(row.get('train_score', 0.0))} | "
                f"{_fmt(row.get('test_score', 0.0))} | {_fmt(row.get('test_total_return_pct', 0.0))}% | "
                f"{_fmt(row.get('test_max_drawdown_pct', 0.0))}% | {row.get('test_trade_count', 0)} | "
                f"{row.get('overfit_label', '')} |"
            )
        lines.append("")

    lines += [
        "## Research-only limitation",
        "",
        "Walk-forward validation is stronger than a single in-sample test, but it is still historical simulation. It is not a guarantee of future performance and is not live trading advice.",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def render_symbol_leaderboard(payload: dict[str, Any]) -> str:
    lines = [
        "# Walk-Forward Symbol Leaderboard",
        "",
        "| Rank | Symbol | Best candidate | Test score | Test objective hit | Test progress | Buy-hold test | Overfit label |",
        "|---:|---|---|---:|---|---:|---:|---|",
    ]
    for rank, row in enumerate(payload.get("ranked_symbols") or [], start=1):
        lines.append(
            f"| {rank} | {row.get('symbol')} | {row.get('best_candidate_id', '')} | "
            f"{_fmt(row.get('best_test_score', 0.0))} | {row.get('best_test_objective_hit', False)} | "
            f"{_fmt(row.get('best_test_objective_progress_pct', 0.0))}% | "
            f"{_fmt(row.get('buy_hold_test_return_pct', 0.0))}% | {row.get('best_overfit_label', '')} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def render_overfit_warning_report(payload: dict[str, Any]) -> str:
    rows = payload.get("ranked_validated_candidates") or []
    rows = sorted(rows, key=lambda item: _safe_float(item.get("train_score", 0.0)) - _safe_float(item.get("test_score", 0.0)), reverse=True)

    lines = [
        "# Walk-Forward Overfit Warning Report",
        "",
        "This report flags strategies that looked strong on train data but weakened on test data.",
        "",
        "| Rank | Symbol | Candidate | Train score | Test score | Score drop | Train progress | Test progress | Label |",
        "|---:|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for rank, row in enumerate(rows[:50], start=1):
        train_score = _safe_float(row.get("train_score", 0.0))
        test_score = _safe_float(row.get("test_score", 0.0))
        lines.append(
            f"| {rank} | {row.get('symbol')} | {row.get('candidate_id')} | "
            f"{_fmt(train_score)} | {_fmt(test_score)} | {_fmt(train_score - test_score)} | "
            f"{_fmt(row.get('train_objective_progress_pct', 0.0))}% | "
            f"{_fmt(row.get('test_objective_progress_pct', 0.0))}% | {row.get('overfit_label', '')} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def render_top_walk_forward_strategy_algorithm(payload: dict[str, Any]) -> str:
    rows = payload.get("ranked_validated_candidates") or []
    if not rows:
        return "# Top Walk-Forward Strategy Algorithm\n\nNo validated candidates available.\n"

    top = rows[0]
    lines = [
        "# Top Walk-Forward Strategy Algorithm",
        "",
        "Research/simulation-only. This is the highest-ranked test-window candidate from walk-forward validation.",
        "",
        f"- symbol: {top.get('symbol')}",
        f"- candidate: `{top.get('candidate_id')}`",
        f"- train_score: {_fmt(top.get('train_score', 0.0))}",
        f"- test_score: {_fmt(top.get('test_score', 0.0))}",
        f"- train_objective_hit: {top.get('train_objective_hit', False)}",
        f"- test_objective_hit: {top.get('test_objective_hit', False)}",
        f"- test_objective_progress_pct: {_fmt(top.get('test_objective_progress_pct', 0.0))}%",
        f"- buy_hold_test_return_pct: {_fmt(top.get('buy_hold_test_return_pct', 0.0))}%",
        f"- overfit_label: {top.get('overfit_label', '')}",
        "",
        "## Strategy code",
        "",
        "```text",
        top.get("script", ""),
        "```",
        "",
        "## Deterministic interpretation",
        "",
    ]

    if top.get("test_objective_hit"):
        lines.append("- The strategy reached the objective on the unseen test window.")
    else:
        lines.append("- The strategy did not reach the objective on the unseen test window.")

    if top.get("overfit_label") == "walk_forward_pass":
        lines.append("- Train and test windows both survived the objective check.")
    elif "overfit" in str(top.get("overfit_label", "")):
        lines.append("- Train performance weakened materially on the test window; treat as potential overfit.")
    else:
        lines.append("- The candidate partially survived but needs additional rolling windows and stress tests.")

    lines += [
        "- Next step: run rolling walk-forward windows and add slippage/fee stress testing.",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def write_walk_forward_artifacts(payload: dict[str, Any], out_dir: str | Path) -> dict[str, str]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "walk_forward_universe_results_json": out_dir / "walk_forward_universe_results.json",
        "walk_forward_universe_report_md": out_dir / "walk_forward_universe_report.md",
        "walk_forward_symbol_leaderboard_md": out_dir / "walk_forward_symbol_leaderboard.md",
        "overfit_warning_report_md": out_dir / "overfit_warning_report.md",
        "top_walk_forward_strategy_algorithm_md": out_dir / "top_walk_forward_strategy_algorithm.md",
    }

    paths["walk_forward_universe_results_json"].write_text(json.dumps(payload, indent=2), encoding="utf-8")
    paths["walk_forward_universe_report_md"].write_text(render_walk_forward_report(payload), encoding="utf-8")
    paths["walk_forward_symbol_leaderboard_md"].write_text(render_symbol_leaderboard(payload), encoding="utf-8")
    paths["overfit_warning_report_md"].write_text(render_overfit_warning_report(payload), encoding="utf-8")
    paths["top_walk_forward_strategy_algorithm_md"].write_text(render_top_walk_forward_strategy_algorithm(payload), encoding="utf-8")

    return {key: str(value) for key, value in paths.items()}
