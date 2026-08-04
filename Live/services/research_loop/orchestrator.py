from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .memory_feedback import write_memory_feedback
from .models import ResearchLoopConfig, ResearchLoopResult, make_id, utc_now_iso
from .evaluation_pipeline import evaluate_candidate_for_loop
from .strategy_candidate_generator import generate_strategy_candidates


def _repo_root(start: str | Path | None = None) -> Path:
    if start:
        return Path(start).resolve()
    p = Path.cwd().resolve()
    for c in [p, *p.parents]:
        if (c / "Live" / "app.py").exists():
            return c
        if c.name.lower() == "live" and (c / "app.py").exists():
            return c.parent
    return p.parent if p.name.lower() == "live" else p


def _slug(text: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in text)
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_")[:64] or "research_loop"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _json_text(value: Any) -> str:
    return json.dumps(_json_safe(value), sort_keys=True, allow_nan=False)


def _write_reports(repo: Path, result_payload: dict[str, Any], loop_id: str, theme: str) -> dict[str, str]:
    date_part = datetime.now().astimezone().strftime("%Y-%m-%d")
    out_dir = repo / "Live" / "data" / "research_loop" / "reports" / date_part
    out_dir.mkdir(parents=True, exist_ok=True)

    base = f"{loop_id}_{_slug(theme)}"
    json_path = out_dir / f"{base}.json"
    md_path = out_dir / f"{base}.md"

    json_path.write_text(json.dumps(_json_safe(result_payload), indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_build_report_markdown(result_payload), encoding="utf-8")

    # Best-effort registration with Artifact Writer. This should never break the loop.
    try:
        from services.artifacts.artifact_writer import register_existing_file
        try:
            register_existing_file(path=json_path, repo_root=str(repo), module="research_loop", artifact_type="loop_report")
            register_existing_file(path=md_path, repo_root=str(repo), module="research_loop", artifact_type="loop_report")
        except TypeError:
            register_existing_file(str(json_path))
            register_existing_file(str(md_path))
    except Exception:
        pass

    return {"json": str(json_path), "markdown": str(md_path)}


def _build_report_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    loop_id = payload.get("loop_id")
    config = payload.get("config", {})
    evaluations = payload.get("evaluations", [])
    survivors = payload.get("survivors", [])

    lines.append(f"# Research Loop Report — {loop_id}")
    lines.append("")
    lines.append("Research/simulation only. No broker calls or live orders.")
    lines.append("")
    lines.append("## Executive summary")
    lines.append("")
    lines.append(f"- Theme: `{config.get('theme')}`")
    lines.append(f"- Symbols: `{', '.join(config.get('symbols', []))}`")
    lines.append(f"- Backend: `{config.get('backend')}`")
    lines.append(f"- Mode: `{config.get('mode', 'simulation_only')}`")
    lines.append(f"- Status: `{payload.get('status')}`")
    lines.append(f"- Quant persist: `{payload.get('quant_persist_status')}`")
    lines.append(f"- Candidates tested: `{len(evaluations)}`")
    lines.append(f"- Survivors: `{len(survivors)}`")
    lines.append("")

    lines.append("## What this loop does")
    lines.append("")
    lines.append("The Research Loop is the research manager. It chooses a theme/symbol set, generates candidates, evaluates them, scores them, stores results, and writes feedback for the next iteration.")
    lines.append("")
    lines.append("Auto Lab is the experiment worker. The target architecture is for this loop to call Auto Lab, BackTestEngine, walk-forward validation, and universe testing as worker tools.")
    lines.append("")
    lines.append("Current v24.9.2 status: deterministic proxy evaluation is still active. This report is useful for testing the orchestration and scoring path, but it is not yet a real historical backtest.")
    lines.append("")

    lines.append("## Research gates")
    lines.append("")
    lines.append("| Gate | Required value |")
    lines.append("| --- | ---: |")
    lines.append(f"| Minimum trades | `{config.get('min_trades')}` |")
    lines.append(f"| Max drawdown limit | `{config.get('max_drawdown_limit')}` |")
    lines.append(f"| Minimum Sharpe | `{config.get('min_sharpe')}` |")
    lines.append("| Universe pass rate | `>= 0.34` |")
    lines.append("| Walk-forward proxy | `avg_sharpe >= min_sharpe * 0.75` |")
    lines.append("")

    ranked = sorted(evaluations, key=lambda item: item.get("score", 0), reverse=True)
    lines.append("## Candidate rankings")
    lines.append("")
    lines.append("| Rank | Strategy | Family | Status | Score | Avg Sharpe | Return | Drawdown | Trades | Reasons |")
    lines.append("| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |")
    for idx, item in enumerate(ranked, 1):
        candidate = item.get("candidate", {})
        metrics = item.get("aggregate_metrics", {})
        reasons = ", ".join(item.get("rejection_reasons", []))
        lines.append(
            f"| {idx} | {candidate.get('strategy_name')} | {candidate.get('strategy_family')} | "
            f"{item.get('status')} | {item.get('score')} | {metrics.get('avg_sharpe')} | "
            f"{metrics.get('avg_total_return')} | {metrics.get('worst_drawdown')} | "
            f"{metrics.get('total_trades')} | {reasons} |"
        )
    lines.append("")

    lines.append("## Candidate details")
    lines.append("")
    for idx, item in enumerate(ranked, 1):
        candidate = item.get("candidate", {})
        metrics = item.get("aggregate_metrics", {})
        walk = item.get("walk_forward_metrics", {})
        universe = item.get("universe_metrics", {})
        params = candidate.get("parameters", {})
        symbol_results = item.get("symbol_results", [])

        lines.append(f"### {idx}. {candidate.get('strategy_name')}")
        lines.append("")
        lines.append(f"- Candidate ID: `{candidate.get('candidate_id')}`")
        lines.append(f"- Family: `{candidate.get('strategy_family')}`")
        lines.append(f"- Status: `{item.get('status')}`")
        lines.append(f"- Score: `{item.get('score')}`")
        lines.append(f"- Hypothesis: {candidate.get('hypothesis')}")
        lines.append(f"- Parameters: `{json.dumps(params, sort_keys=True)}`")
        lines.append("")
        lines.append("#### Aggregate metrics")
        lines.append("")
        lines.append(f"- Average total return: `{metrics.get('avg_total_return')}`")
        lines.append(f"- Average Sharpe: `{metrics.get('avg_sharpe')}`")
        lines.append(f"- Worst drawdown: `{metrics.get('worst_drawdown')}`")
        lines.append(f"- Average win rate: `{metrics.get('avg_win_rate')}`")
        lines.append(f"- Average profit factor: `{metrics.get('avg_profit_factor')}`")
        lines.append(f"- Total trades: `{metrics.get('total_trades')}`")
        lines.append("")
        lines.append("#### Walk-forward proxy")
        lines.append("")
        lines.append(f"- Windows: `{walk.get('window_count')}`")
        lines.append(f"- Average Sharpe: `{walk.get('avg_sharpe')}`")
        lines.append(f"- Pass rate: `{walk.get('pass_rate')}`")
        lines.append(f"- Stability score: `{walk.get('stability_score')}`")
        lines.append("")
        lines.append("#### Universe robustness")
        lines.append("")
        lines.append(f"- Symbols tested: `{universe.get('symbols_tested')}`")
        lines.append(f"- Pass rate: `{universe.get('pass_rate')}`")
        lines.append(f"- Passing symbols: `{', '.join(universe.get('pass_symbols', []))}`")
        lines.append("")
        lines.append("#### Per-symbol simulated results")
        lines.append("")
        lines.append("| Symbol | Return | Sharpe | Max DD | Win rate | Trades | Profit factor | Warnings |")
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |")
        for row in symbol_results:
            lines.append(
                f"| {row.get('symbol')} | {row.get('total_return')} | {row.get('sharpe')} | "
                f"{row.get('max_drawdown')} | {row.get('win_rate')} | {row.get('trade_count')} | "
                f"{row.get('profit_factor')} | {', '.join(row.get('warnings', []))} |"
            )
        lines.append("")
        if item.get("rejection_reasons"):
            lines.append(f"Rejected because: `{', '.join(item.get('rejection_reasons', []))}`")
            lines.append("")
        else:
            lines.append("Passed current proxy gates. Next step: real BackTestEngine validation.")
            lines.append("")

    lines.append("## Next recommended action")
    lines.append("")
    if survivors:
        lines.append("1. Run the top survivor candidates through a real BackTestEngine adapter.")
        lines.append("2. Then run walk-forward validation on only the survivors.")
        lines.append("3. Promote only candidates that remain stable out-of-sample.")
    else:
        lines.append("1. No candidates passed all current proxy gates.")
        lines.append("2. Generate a wider candidate set or revise gates.")
        lines.append("3. Prefer strategies with more trades, lower drawdown, and stronger universe pass rate.")
    lines.append("")
    lines.append("## Next integration patch")
    lines.append("")
    lines.append("v24.9.3 — Real BackTestEngine Adapter")
    lines.append("")
    lines.append("The current loop is still using deterministic proxy scoring. The next integration should call the real BackTestEngine through a safe adapter, then store those real simulated backtest results in Quant Schema.")
    lines.append("")
    lines.append("## Safety note")
    lines.append("")
    lines.append("This report is research/simulation only. It does not place trades, route orders, or connect to a broker.")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _db_imports():
    from services.database.config import load_database_config
    try:
        from services.database.backend import connect_database
    except Exception:
        from services.database.connections import connect_database  # type: ignore
    from services.quant_schema.migrations import migrate_quant_schema
    return load_database_config, connect_database, migrate_quant_schema


def _raw_connection(db: Any) -> Any:
    for attr in ("conn", "connection", "_conn", "_connection"):
        if hasattr(db, attr):
            return getattr(db, attr)
    return db


def _db_module(conn: Any) -> str:
    return str(getattr(conn.__class__, "__module__", ""))


def _is_postgres(conn: Any) -> bool:
    mod = _db_module(conn).lower()
    return "psycopg" in mod or "postgres" in mod


def _placeholder(conn: Any) -> str:
    return "%s" if _is_postgres(conn) else "?"


def _quote_ident(name: str) -> str:
    safe = "".join(ch for ch in str(name) if ch.isalnum() or ch == "_")
    if not safe:
        raise ValueError("empty identifier")
    return f'"{safe}"'


def _execute(conn: Any, sql: str, params: tuple[Any, ...] = ()):
    if hasattr(conn, "execute"):
        return conn.execute(sql, params)
    cur = conn.cursor()
    cur.execute(sql, params)
    return cur


def _rollback(conn: Any) -> None:
    try:
        conn.rollback()
    except Exception:
        pass


def _table_columns(conn: Any, table: str) -> dict[str, str]:
    """Return {column_name: declared_type}. Works for SQLite and best-effort PostgreSQL."""
    columns: dict[str, str] = {}

    try:
        cur = _execute(conn, f"PRAGMA table_info({_quote_ident(table)})")
        for row in cur.fetchall():
            # SQLite rows: cid, name, type, notnull, dflt_value, pk
            name = row[1] if not isinstance(row, dict) else row.get("name")
            col_type = row[2] if not isinstance(row, dict) else row.get("type", "")
            if name:
                columns[str(name)] = str(col_type or "")
        if columns:
            return columns
    except Exception:
        _rollback(conn)

    try:
        ph = _placeholder(conn)
        cur = _execute(
            conn,
            "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = " + ph,
            (table,),
        )
        for row in cur.fetchall():
            if isinstance(row, dict):
                name = row.get("column_name")
                col_type = row.get("data_type", "")
            else:
                name = row[0]
                col_type = row[1] if len(row) > 1 else ""
            if name:
                columns[str(name)] = str(col_type or "")
    except Exception:
        _rollback(conn)

    return columns


def _adapt_value_for_db(conn: Any, value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        if _is_postgres(conn):
            try:
                from psycopg.types.json import Jsonb
                return Jsonb(_json_safe(value))
            except Exception:
                return _json_text(value)
        return _json_text(value)
    return value


def _insert_compatible(conn: Any, table: str, values: dict[str, Any]) -> tuple[bool, str]:
    columns = _table_columns(conn, table)
    if not columns:
        return False, f"{table}: table not found or no readable columns"

    # Avoid overriding auto-increment PKs named id.
    usable: dict[str, Any] = {}
    lower_to_actual = {name.lower(): name for name in columns}

    for key, value in values.items():
        actual = lower_to_actual.get(str(key).lower())
        if actual and actual.lower() != "id":
            usable[actual] = value

    # If older tables use generic names, map core fields safely.
    alias_pairs = [
        ("run_id", "experiment_id"),
        ("name", "experiment_name"),
        ("type", "module"),
        ("payload_json", "metrics"),
        ("metadata_json", "details"),
        ("config_json", "config"),
        ("params_json", "parameters"),
        ("created", "created_at"),
        ("timestamp", "created_at"),
    ]
    for target, source in alias_pairs:
        actual = lower_to_actual.get(target.lower())
        if actual and actual.lower() != "id" and actual not in usable and source in values:
            usable[actual] = values[source]

    if not usable:
        return False, f"{table}: no compatible columns among {sorted(columns)}"

    names = list(usable.keys())
    placeholders = ", ".join([_placeholder(conn)] * len(names))
    sql = f"INSERT INTO {_quote_ident(table)} ({', '.join(_quote_ident(name) for name in names)}) VALUES ({placeholders})"
    params = tuple(_adapt_value_for_db(conn, usable[name]) for name in names)

    try:
        _execute(conn, sql, params)
        return True, f"{table}: inserted {len(names)} columns"
    except Exception as exc:
        _rollback(conn)
        return False, f"{table}: {type(exc).__name__}: {exc}"


def _persist_to_quant_schema(repo: Path, result: ResearchLoopResult) -> str:
    """Persist using schema-compatible inserts.

    This avoids failures when an older Data Catalog table named experiment_runs
    already exists without the newer typed Quant Schema column experiment_id.
    """
    try:
        load_database_config, connect_database, migrate_quant_schema = _db_imports()
        db_config = load_database_config(repo_root=str(repo), backend=result.config.backend)
        artifact_id = result.report_paths.get("json", result.loop_id)

        messages: list[str] = []
        inserted = 0

        with connect_database(db_config) as db:
            try:
                migrate_quant_schema(db)
            except Exception as exc:
                messages.append(f"migration warning: {type(exc).__name__}: {exc}")

            conn = _raw_connection(db)

            experiment_values = {
                "experiment_id": result.loop_id,
                "run_id": result.loop_id,
                "module": "research_loop",
                "experiment_name": f"Research Loop: {result.config.theme}",
                "name": f"Research Loop: {result.config.theme}",
                "status": result.status,
                "config": result.config.to_dict(),
                "config_json": result.config.to_dict(),
                "artifact_id": artifact_id,
                "created_at": result.started_at,
                "updated_at": result.finished_at,
            }
            ok, msg = _insert_compatible(conn, "experiment_runs", experiment_values)
            messages.append(msg)
            inserted += int(ok)

            for evaluation in result.evaluations:
                candidate = evaluation.candidate
                primary_symbol = (candidate.symbols or result.config.normalized_symbols() or ["MULTI"])[0]
                strategy_run_id = f"strat_{candidate.candidate_id}"

                strategy_values = {
                    "strategy_run_id": strategy_run_id,
                    "run_id": strategy_run_id,
                    "experiment_id": result.loop_id,
                    "artifact_id": artifact_id,
                    "strategy_name": candidate.strategy_name,
                    "name": candidate.strategy_name,
                    "strategy_family": candidate.strategy_family,
                    "family": candidate.strategy_family,
                    "symbol": primary_symbol,
                    "timeframe": candidate.timeframe,
                    "parameters": candidate.parameters,
                    "params_json": candidate.parameters,
                    "status": evaluation.status,
                    "created_at": evaluation.evaluated_at,
                }
                ok, msg = _insert_compatible(conn, "strategy_runs", strategy_values)
                messages.append(msg)
                inserted += int(ok)

                for symbol_result in evaluation.symbol_results:
                    bt_id = f"bt_{candidate.candidate_id}_{symbol_result.symbol}"
                    metrics = {
                        "profit_factor": symbol_result.profit_factor,
                        "data_quality": symbol_result.data_quality,
                        "warnings": symbol_result.warnings,
                        "candidate_score": evaluation.score,
                        "simulation_only": True,
                        "proxy_evaluation": True,
                    }
                    backtest_values = {
                        "backtest_run_id": bt_id,
                        "run_id": bt_id,
                        "strategy_run_id": strategy_run_id,
                        "experiment_id": result.loop_id,
                        "artifact_id": artifact_id,
                        "symbol": symbol_result.symbol,
                        "strategy_name": candidate.strategy_name,
                        "timeframe": candidate.timeframe,
                        "sharpe": symbol_result.sharpe,
                        "max_drawdown": symbol_result.max_drawdown,
                        "win_rate": symbol_result.win_rate,
                        "total_return": symbol_result.total_return,
                        "trade_count": symbol_result.trade_count,
                        "profit_factor": symbol_result.profit_factor,
                        "status": evaluation.status,
                        "metrics": metrics,
                        "payload_json": metrics,
                        "created_at": evaluation.evaluated_at,
                    }
                    ok, msg = _insert_compatible(conn, "backtest_runs", backtest_values)
                    messages.append(msg)
                    inserted += int(ok)

                wf_id = f"wf_{candidate.candidate_id}"
                walk_values = {
                    "walk_forward_run_id": wf_id,
                    "run_id": wf_id,
                    "experiment_id": result.loop_id,
                    "artifact_id": artifact_id,
                    "symbol": primary_symbol,
                    "strategy_name": candidate.strategy_name,
                    "timeframe": candidate.timeframe,
                    "window_count": evaluation.walk_forward_metrics.get("window_count", 3),
                    "avg_sharpe": evaluation.walk_forward_metrics.get("avg_sharpe", 0.0),
                    "pass_rate": evaluation.walk_forward_metrics.get("pass_rate", 0.0),
                    "stability_score": evaluation.walk_forward_metrics.get("stability_score", 0.0),
                    "status": evaluation.status,
                    "metrics": {**evaluation.walk_forward_metrics, "simulation_only": True, "proxy_evaluation": True},
                    "payload_json": {**evaluation.walk_forward_metrics, "simulation_only": True, "proxy_evaluation": True},
                    "created_at": evaluation.evaluated_at,
                }
                ok, msg = _insert_compatible(conn, "walk_forward_runs", walk_values)
                messages.append(msg)
                inserted += int(ok)

                if evaluation.warnings or evaluation.rejection_reasons:
                    dq_id = f"dq_{candidate.candidate_id}"
                    details = {
                        "warnings": evaluation.warnings,
                        "rejection_reasons": evaluation.rejection_reasons,
                        "simulation_only": True,
                        "proxy_evaluation": True,
                    }
                    dq_values = {
                        "event_id": dq_id,
                        "run_id": dq_id,
                        "artifact_id": artifact_id,
                        "symbol": ",".join(candidate.symbols),
                        "dataset_name": "research_loop_proxy",
                        "severity": "warn" if evaluation.status == "PASS" else "info",
                        "event_type": "research_loop_filter",
                        "message": "; ".join((evaluation.rejection_reasons or evaluation.warnings)[:5]),
                        "details": details,
                        "metadata_json": details,
                        "created_at": evaluation.evaluated_at,
                    }
                    ok, msg = _insert_compatible(conn, "data_quality_events", dq_values)
                    messages.append(msg)
                    inserted += int(ok)

            ranking = [
                {
                    "strategy_name": ev.candidate.strategy_name,
                    "strategy_family": ev.candidate.strategy_family,
                    "score": ev.score,
                    "status": ev.status,
                }
                for ev in sorted(result.evaluations, key=lambda item: item.score, reverse=True)
            ]
            uni_id = f"uni_{result.loop_id}"
            universe_values = {
                "universe_run_id": uni_id,
                "run_id": uni_id,
                "experiment_id": result.loop_id,
                "artifact_id": artifact_id,
                "universe_name": f"Research Loop Universe: {result.config.theme}",
                "name": f"Research Loop Universe: {result.config.theme}",
                "theme": result.config.theme,
                "symbols": result.config.normalized_symbols(),
                "symbols_json": result.config.normalized_symbols(),
                "selected_count": len(result.survivors),
                "ranking": ranking,
                "payload_json": ranking,
                "status": result.status,
                "created_at": result.finished_at,
            }
            ok, msg = _insert_compatible(conn, "universe_runs", universe_values)
            messages.append(msg)
            inserted += int(ok)

            try:
                if hasattr(db, "commit"):
                    db.commit()
                elif hasattr(db, "conn"):
                    db.conn.commit()
                elif hasattr(conn, "commit"):
                    conn.commit()
            except Exception:
                pass

        if inserted:
            return f"PASS: inserted {inserted} compatible research rows"
        return "WARN: no compatible quant rows inserted; " + " | ".join(messages[:8])
    except Exception as exc:
        return f"WARN: quant schema persist skipped: {type(exc).__name__}: {exc}"


def run_research_loop(config: ResearchLoopConfig) -> ResearchLoopResult:
    started_at = utc_now_iso()
    repo = _repo_root(config.repo_root)
    config.repo_root = str(repo)

    loop_id = make_id("research_loop")
    errors: list[str] = []

    candidates = generate_strategy_candidates(config)
    evaluations = [evaluate_candidate_for_loop(config, candidate) for candidate in candidates]
    survivors = [
        item for item in sorted(evaluations, key=lambda ev: ev.score, reverse=True)
        if item.status == "PASS"
    ]

    status = "PASS" if survivors else "WARN"

    temp_result = ResearchLoopResult(
        loop_id=loop_id,
        config=config,
        candidates=candidates,
        evaluations=evaluations,
        survivors=survivors,
        report_paths={},
        quant_persist_status="PENDING",
        feedback_path="",
        started_at=started_at,
        finished_at=utc_now_iso(),
        status=status,
        errors=errors,
    )

    report_paths = _write_reports(repo, temp_result.to_dict(), loop_id, config.theme)
    temp_result.report_paths = report_paths
    quant_status = _persist_to_quant_schema(repo, temp_result)
    temp_result.quant_persist_status = quant_status
    feedback_path = write_memory_feedback(temp_result)
    temp_result.feedback_path = feedback_path
    temp_result.finished_at = utc_now_iso()

    report_paths = _write_reports(repo, temp_result.to_dict(), loop_id, config.theme)
    temp_result.report_paths = report_paths

    return temp_result


def _parse_symbols(value: str) -> list[str]:
    return [part.strip().upper() for part in str(value or "").split(",") if part.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run simulation-only strategy/backtest research loop.")
    parser.add_argument("--repo-root", type=str, default=None)
    parser.add_argument("--theme", type=str, default="AI infrastructure semiconductors")
    parser.add_argument("--symbols", type=str, default="AMD,NVDA,SMH")
    parser.add_argument("--max-candidates", type=int, default=10)
    parser.add_argument("--max-loops", type=int, default=1)
    parser.add_argument("--min-trades", type=int, default=10)
    parser.add_argument("--max-drawdown-limit", type=float, default=-0.20)
    parser.add_argument("--min-sharpe", type=float, default=0.25)
    parser.add_argument("--backend", choices=["sqlite", "postgres"], default="sqlite")
    parser.add_argument("--timeframe", type=str, default="1d")
    parser.add_argument("--evaluation-mode", choices=["proxy", "hybrid_safe", "real_required"], default="hybrid_safe")
    args = parser.parse_args()

    config = ResearchLoopConfig(
        theme=args.theme,
        symbols=_parse_symbols(args.symbols),
        max_candidates=args.max_candidates,
        max_loops=args.max_loops,
        min_trades=args.min_trades,
        max_drawdown_limit=args.max_drawdown_limit,
        min_sharpe=args.min_sharpe,
        backend=args.backend,
        timeframe=args.timeframe,
        evaluation_mode=args.evaluation_mode,
        repo_root=args.repo_root,
    )
    result = run_research_loop(config)

    summary = {
        "status": result.status,
        "loop_id": result.loop_id,
        "theme": result.config.theme,
        "symbols": result.config.normalized_symbols(),
        "candidates": len(result.candidates),
        "survivors": len(result.survivors),
        "quant_persist_status": result.quant_persist_status,
        "report_paths": result.report_paths,
        "feedback_path": result.feedback_path,
        "top_candidates": [
            {
                "strategy_name": item.candidate.strategy_name,
                "family": item.candidate.strategy_family,
                "score": item.score,
                "status": item.status,
            }
            for item in sorted(result.evaluations, key=lambda ev: ev.score, reverse=True)[:5]
        ],
        "safety": "simulation_only_no_broker_no_orders",
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if result.status in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
