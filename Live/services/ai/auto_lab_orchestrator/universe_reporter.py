from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
from typing import Any
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


def _best_result_for_symbol(symbol_result: dict[str, Any]) -> dict[str, Any]:
    candidates = symbol_result.get("ranked_mutations") or []
    return candidates[0] if candidates else {}


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def build_universe_payload(
    *,
    universe_run_id: str,
    symbols: list[str],
    settings: dict[str, Any],
    symbol_results: list[dict[str, Any]],
) -> dict[str, Any]:
    ranked_symbols = sorted(
        symbol_results,
        key=lambda item: _safe_float((_best_result_for_symbol(item) or {}).get("score"), 0.0),
        reverse=True,
    )

    robustness: dict[str, dict[str, Any]] = {}
    for symbol_result in symbol_results:
        symbol = symbol_result.get("symbol", "")
        for row in symbol_result.get("ranked_mutations") or []:
            strategy_key = row.get("strategy_family") or row.get("candidate_id") or "unknown"
            bucket = robustness.setdefault(
                strategy_key,
                {
                    "strategy_key": strategy_key,
                    "symbols_tested": 0,
                    "symbols_research_pass": 0,
                    "symbols_objective_hit": 0,
                    "scores": [],
                    "progress_values": [],
                    "symbols": [],
                },
            )
            bucket["symbols_tested"] += 1
            bucket["symbols"].append(symbol)
            if row.get("research_pass"):
                bucket["symbols_research_pass"] += 1
            if row.get("objective_hit"):
                bucket["symbols_objective_hit"] += 1
            bucket["scores"].append(_safe_float(row.get("score"), 0.0))
            bucket["progress_values"].append(_safe_float(row.get("objective_progress_pct"), 0.0))

    robustness_rows = []
    for bucket in robustness.values():
        scores = bucket["scores"]
        progress = bucket["progress_values"]
        row = {
            "strategy_key": bucket["strategy_key"],
            "symbols_tested": bucket["symbols_tested"],
            "symbols_research_pass": bucket["symbols_research_pass"],
            "symbols_objective_hit": bucket["symbols_objective_hit"],
            "avg_score": round(sum(scores) / len(scores), 4) if scores else 0.0,
            "avg_objective_progress_pct": round(sum(progress) / len(progress), 4) if progress else 0.0,
            "symbols": bucket["symbols"],
        }
        robustness_rows.append(row)

    robustness_rows = sorted(
        robustness_rows,
        key=lambda item: (item["symbols_research_pass"], item["symbols_objective_hit"], item["avg_score"]),
        reverse=True,
    )

    return {
        "schema_version": "universe_results_v21_5",
        "universe_run_id": universe_run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "symbols": symbols,
        "settings": settings,
        "symbol_results": symbol_results,
        "ranked_symbols": ranked_symbols,
        "strategy_robustness": robustness_rows,
        "safety": {
            "simulation_only": True,
            "broker_calls": False,
            "live_orders": False,
            "note": "Universe runner is research/simulation-only.",
        },
    }


def render_universe_report(payload: dict[str, Any]) -> str:
    lines = [
        "# AI Auto Lab Multi-Symbol Universe Report",
        "",
        "AI Auto Lab is research/simulation-only. It does not place orders, connect to brokers, or provide personalized financial advice.",
        "",
        "## Run",
        "",
        f"- universe_run_id: `{payload.get('universe_run_id')}`",
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
        "## Symbol leaderboard",
        "",
        "| Rank | Symbol | Best candidate | Score | Research | Objective | Progress | Return | Run dir |",
        "|---:|---|---|---:|---|---|---:|---:|---|",
    ]

    for rank, symbol_result in enumerate(payload.get("ranked_symbols") or [], start=1):
        best = _best_result_for_symbol(symbol_result)
        lines.append(
            f"| {rank} | {symbol_result.get('symbol')} | {best.get('candidate_id', '')} | "
            f"{_fmt(best.get('score', 0.0))} | {best.get('research_pass', False)} | "
            f"{best.get('objective_hit', False)} | {_fmt(best.get('objective_progress_pct', 0.0))}% | "
            f"{_fmt(best.get('total_return_pct', 0.0))}% | {symbol_result.get('run_dir', '')} |"
        )

    lines += [
        "",
        "## Strategy robustness summary",
        "",
        "| Rank | Strategy key | Symbols tested | Research pass symbols | Objective hit symbols | Avg score | Avg progress | Symbols |",
        "|---:|---|---:|---:|---:|---:|---:|---|",
    ]

    for rank, row in enumerate(payload.get("strategy_robustness") or [], start=1):
        lines.append(
            f"| {rank} | {row.get('strategy_key')} | {row.get('symbols_tested')} | "
            f"{row.get('symbols_research_pass')} | {row.get('symbols_objective_hit')} | "
            f"{_fmt(row.get('avg_score', 0.0))} | {_fmt(row.get('avg_objective_progress_pct', 0.0))}% | "
            f"{', '.join(row.get('symbols') or [])} |"
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
            f"- row_count: {symbol_result.get('row_count')}",
            f"- first_date: {symbol_result.get('first_date')}",
            f"- last_date: {symbol_result.get('last_date')}",
            f"- baseline_research_pass_parents: {symbol_result.get('baseline_research_pass_parents')}",
            f"- mutation_count: {symbol_result.get('mutation_count')}",
            f"- research_pass_count: {symbol_result.get('research_pass_count')}",
            f"- objective_hit_count: {symbol_result.get('objective_hit_count')}",
            "",
            "| Rank | Candidate | Score | Research | Objective | Progress | Return | Drawdown | Trades |",
            "|---:|---|---:|---|---|---:|---:|---:|---:|",
        ]
        for rank, row in enumerate((symbol_result.get("ranked_mutations") or [])[:10], start=1):
            lines.append(
                f"| {rank} | {row.get('candidate_id')} | {_fmt(row.get('score', 0.0))} | "
                f"{row.get('research_pass', False)} | {row.get('objective_hit', False)} | "
                f"{_fmt(row.get('objective_progress_pct', 0.0))}% | {_fmt(row.get('total_return_pct', 0.0))}% | "
                f"{_fmt(row.get('max_drawdown_pct', 0.0))}% | {row.get('trade_count', 0)} |"
            )
        lines.append("")

    lines += [
        "## Research-only limitation",
        "",
        "This universe report is in-sample/simulated research unless paired with walk-forward validation. It is not a guarantee of future results and is not live trading advice.",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def render_symbol_leaderboard(payload: dict[str, Any]) -> str:
    lines = [
        "# Symbol Leaderboard",
        "",
        "| Rank | Symbol | Best candidate | Score | Objective hit | Progress | Return |",
        "|---:|---|---|---:|---|---:|---:|",
    ]
    for rank, symbol_result in enumerate(payload.get("ranked_symbols") or [], start=1):
        best = _best_result_for_symbol(symbol_result)
        lines.append(
            f"| {rank} | {symbol_result.get('symbol')} | {best.get('candidate_id', '')} | "
            f"{_fmt(best.get('score', 0.0))} | {best.get('objective_hit', False)} | "
            f"{_fmt(best.get('objective_progress_pct', 0.0))}% | {_fmt(best.get('total_return_pct', 0.0))}% |"
        )
    return "\n".join(lines).rstrip() + "\n"


def render_strategy_robustness_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Strategy Robustness Report",
        "",
        "This report checks which strategy families appear across multiple symbols. Cross-symbol strength is not the same as walk-forward validation, but it helps detect single-symbol overfit risk.",
        "",
        "| Rank | Strategy key | Symbols tested | Research pass symbols | Objective hit symbols | Avg score | Avg progress | Symbols |",
        "|---:|---|---:|---:|---:|---:|---:|---|",
    ]
    for rank, row in enumerate(payload.get("strategy_robustness") or [], start=1):
        lines.append(
            f"| {rank} | {row.get('strategy_key')} | {row.get('symbols_tested')} | "
            f"{row.get('symbols_research_pass')} | {row.get('symbols_objective_hit')} | "
            f"{_fmt(row.get('avg_score', 0.0))} | {_fmt(row.get('avg_objective_progress_pct', 0.0))}% | "
            f"{', '.join(row.get('symbols') or [])} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def render_top_universe_strategy_algorithm(payload: dict[str, Any]) -> str:
    ranked = payload.get("ranked_symbols") or []
    if not ranked:
        return "# Top Universe Strategy Algorithm\n\nNo symbol results available.\n"

    best_symbol = ranked[0]
    best = _best_result_for_symbol(best_symbol)
    algorithm_text = best_symbol.get("top_strategy_algorithm_text") or ""

    lines = [
        "# Top Universe Strategy Algorithm",
        "",
        "Research/simulation-only. This is the highest-ranked in-sample universe result, not a live trading recommendation.",
        "",
        f"- symbol: {best_symbol.get('symbol')}",
        f"- candidate: `{best.get('candidate_id', '')}`",
        f"- score: {_fmt(best.get('score', 0.0))}",
        f"- objective_hit: {best.get('objective_hit', False)}",
        f"- objective_progress_pct: {_fmt(best.get('objective_progress_pct', 0.0))}%",
        f"- total_return_pct: {_fmt(best.get('total_return_pct', 0.0))}%",
        "",
        "## Per-symbol top strategy algorithm",
        "",
    ]
    if algorithm_text:
        lines.append(algorithm_text)
    else:
        lines.append("No top_strategy_algorithm.md content found for the best symbol run.")

    lines += [
        "",
        "## Next validation step",
        "",
        "- Run walk-forward validation so the top in-sample winner is tested on unseen data.",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def write_universe_artifacts(payload: dict[str, Any], out_dir: str | Path) -> dict[str, str]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "universe_results_json": out_dir / "universe_results.json",
        "universe_report_md": out_dir / "universe_report.md",
        "symbol_leaderboard_md": out_dir / "symbol_leaderboard.md",
        "strategy_robustness_report_md": out_dir / "strategy_robustness_report.md",
        "top_universe_strategy_algorithm_md": out_dir / "top_universe_strategy_algorithm.md",
    }

    paths["universe_results_json"].write_text(json.dumps(payload, indent=2), encoding="utf-8")
    paths["universe_report_md"].write_text(render_universe_report(payload), encoding="utf-8")
    paths["symbol_leaderboard_md"].write_text(render_symbol_leaderboard(payload), encoding="utf-8")
    paths["strategy_robustness_report_md"].write_text(render_strategy_robustness_report(payload), encoding="utf-8")
    paths["top_universe_strategy_algorithm_md"].write_text(render_top_universe_strategy_algorithm(payload), encoding="utf-8")

    return {key: str(value) for key, value in paths.items()}
