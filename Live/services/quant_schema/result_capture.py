from __future__ import annotations
from contextlib import contextmanager

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
from typing import Any
import uuid


@dataclass
class CaptureResult:
    status: str
    category: str
    artifact_id: str | None = None
    artifact_path: str | None = None
    quant_backend: str | None = None
    typed_rows: dict[str, str] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


SYMBOL_NOISE = {
    "AI", "ML", "RSI", "BUY", "SELL", "PASS", "FAIL", "WARN", "INFO", "LIVE", "ENV",
    "JSON", "CSV", "DATA", "RUN", "TEST", "AUTO", "LAB", "BACKTEST", "RESULT",
    "RESULTS", "MARKET", "MEMORY", "PACKET", "REPORT", "WALK", "FORWARD",
}

_CAPTURE_ACTIVE = False


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_json(value: Any, depth: int = 0, max_depth: int = 8, _seen: set[int] | None = None) -> Any:
    """Convert arbitrary research output into JSON-safe data.

    This version is recursion-safe. Complex app/runtime objects may contain
    cycles, parent references, callback references, or repeated objects.
    """
    if _seen is None:
        _seen = set()

    if depth > max_depth:
        return repr(value)[:500]

    if value is None or isinstance(value, (str, int, bool)):
        return value

    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value

    complex_like = isinstance(value, (dict, list, tuple, set)) or hasattr(value, "to_dict") or hasattr(value, "__dict__")
    if complex_like:
        oid = id(value)
        if oid in _seen:
            return "<recursive_ref>"
        _seen.add(oid)

    try:
        if isinstance(value, dict):
            out: dict[str, Any] = {}
            for idx, (k, v) in enumerate(value.items()):
                if idx >= 250:
                    out["_truncated_keys"] = True
                    break
                out[str(k)] = _safe_json(v, depth + 1, max_depth, _seen)
            return out

        if isinstance(value, (list, tuple, set)):
            return [_safe_json(v, depth + 1, max_depth, _seen) for v in list(value)[:250]]

        if hasattr(value, "to_dict"):
            try:
                return _safe_json(value.to_dict(), depth + 1, max_depth, _seen)
            except RecursionError:
                return "<recursive_to_dict>"
            except Exception:
                pass

        if hasattr(value, "to_json"):
            try:
                return json.loads(value.to_json())
            except RecursionError:
                return "<recursive_to_json>"
            except Exception:
                pass

        if hasattr(value, "__dict__") and not isinstance(value, type):
            try:
                shallow = {
                    key: item
                    for key, item in vars(value).items()
                    if not str(key).startswith("_")
                }
                return _safe_json(shallow, depth + 1, max_depth, _seen)
            except RecursionError:
                return "<recursive_object>"
            except Exception:
                pass

        return repr(value)[:1000]
    finally:
        if complex_like:
            try:
                _seen.discard(id(value))
            except Exception:
                pass

def _flatten(value: Any, prefix: str = "", out: dict[str, Any] | None = None) -> dict[str, Any]:
    out = out or {}
    if isinstance(value, dict):
        for k, v in value.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, dict):
                _flatten(v, key, out)
            else:
                out[key] = v
    return out


def _first(payload: dict[str, Any], keys: list[str]) -> Any:
    flat = _flatten(payload)
    lower_map = {k.lower().replace(" ", "_").replace("-", "_"): v for k, v in flat.items()}
    for key in keys:
        normalized = key.lower().replace(" ", "_").replace("-", "_")
        if normalized in lower_map:
            return lower_map[normalized]
        for existing, value in lower_map.items():
            if existing.endswith("." + normalized) or existing.endswith("_" + normalized):
                return value
    return None


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        f = float(value)
        return None if math.isnan(f) or math.isinf(f) else f
    except Exception:
        return None


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except Exception:
        return None


def _symbol_from_text(text: str | None) -> str | None:
    if not text:
        return None
    tokens = [token for token in re.split(r"[^A-Za-z0-9]+|_", str(text).upper()) if token]
    for token in tokens:
        if 1 <= len(token) <= 5 and token.isalpha() and token not in SYMBOL_NOISE:
            return token
    return None


def extract_symbol(payload: dict[str, Any], context: dict[str, Any] | None = None) -> str | None:
    context = context or {}
    for key in ["symbol", "ticker", "asset", "primary_symbol"]:
        value = _first(payload, [key])
        if isinstance(value, str):
            symbol = _symbol_from_text(value)
            if symbol:
                return symbol
    for key in ["symbol", "ticker", "name", "method", "module", "artifact_type", "path"]:
        symbol = _symbol_from_text(str(context.get(key) or ""))
        if symbol:
            return symbol
    return None


def extract_strategy_name(payload: dict[str, Any], context: dict[str, Any] | None = None) -> str:
    context = context or {}
    value = _first(payload, ["strategy_name", "strategy", "name", "model_name"])
    if value:
        return str(value)[:120]
    value = context.get("strategy_name") or context.get("method") or context.get("function")
    if value:
        return str(value)[:120]
    return "UnknownStrategy"


def extract_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "timeframe": _first(payload, ["timeframe", "interval", "bar_size"]),
        "start_date": _first(payload, ["start_date", "start", "from_date"]),
        "end_date": _first(payload, ["end_date", "end", "to_date"]),
        "initial_capital": _to_float(_first(payload, ["initial_capital", "starting_capital", "capital"])),
        "ending_capital": _to_float(_first(payload, ["ending_capital", "final_capital", "ending_equity", "final_equity"])),
        "total_return": _to_float(_first(payload, ["total_return", "return", "pct_return"])),
        "cagr": _to_float(_first(payload, ["cagr"])),
        "sharpe": _to_float(_first(payload, ["sharpe", "sharpe_ratio"])),
        "sortino": _to_float(_first(payload, ["sortino", "sortino_ratio"])),
        "max_drawdown": _to_float(_first(payload, ["max_drawdown", "maximum_drawdown", "drawdown"])),
        "win_rate": _to_float(_first(payload, ["win_rate", "winning_rate"])),
        "profit_factor": _to_float(_first(payload, ["profit_factor"])),
        "trade_count": _to_int(_first(payload, ["trade_count", "num_trades", "trades"])),
        "turnover": _to_float(_first(payload, ["turnover"])),
        "fees": _to_float(_first(payload, ["fees", "commissions"])),
        "slippage": _to_float(_first(payload, ["slippage"])),
    }


def _repo_root(start: str | Path | None = None) -> Path:
    p = Path(start or Path.cwd()).resolve()
    for c in [p, *p.parents]:
        if (c / "Live" / "app.py").exists():
            return c
        if c.name.lower() == "live" and (c / "app.py").exists():
            return c.parent
    return p


def _select_backend(preferred: str | None = None) -> str:
    if preferred in {"sqlite", "postgres"}:
        return preferred
    env_backend = os.environ.get("ALGOTRADER_DB_BACKEND", "").lower().strip()
    has_secret = bool(os.environ.get("ALGOTRADER_DB_PASSWORD") or os.environ.get("ALGOTRADER_DATABASE_URL"))
    if env_backend in {"postgres", "postgresql"} and has_secret:
        return "postgres"
    return "sqlite"


@contextmanager
def _db_connect(repo: Path, backend: str):
    """Open the configured database and migrate the quant schema.

    The database backend returns a context manager. Earlier v24.5/v24.6 code
    tried to migrate before entering that context, which could prevent typed
    rows from being written. This wrapper keeps connection lifecycle correct
    for SQLite fallback and optional PostgreSQL.
    """
    from services.database.config import load_database_config
    try:
        from services.database.backend import connect_database
    except Exception:
        from services.database.connections import connect_database  # type: ignore
    from services.quant_schema.migrations import migrate_quant_schema

    config = load_database_config(repo_root=str(repo), backend=backend)
    with connect_database(config) as db:
        migrate_quant_schema(db)
        yield db

def _payload_document(category: str, payload: Any, context: dict[str, Any] | None) -> dict[str, Any]:
    safe_payload = _safe_json(payload)
    if not isinstance(safe_payload, dict):
        safe_payload = {"value": safe_payload}
    return {
        "category": category,
        "captured_at": utc_now(),
        "research_only": True,
        "context": _safe_json(context or {}),
        "payload": safe_payload,
    }


def _capture_research_result_impl(
    *,
    category: str,
    payload: Any,
    context: dict[str, Any] | None = None,
    repo_root: str | Path | None = None,
    preferred_backend: str | None = None,
    ingest_artifact: bool | None = True,
) -> CaptureResult:
    """Capture one research result.

    This function is intentionally best-effort. It should never be used for
    broker execution or live trading. It records research/simulation outputs.
    """
    repo = _repo_root(repo_root)
    context = context or {}
    document = _payload_document(category, payload, context)
    payload_dict = document["payload"] if isinstance(document.get("payload"), dict) else {}

    try:
        from services.artifacts import save_json

        symbol = extract_symbol(payload_dict, context)
        strategy_name = extract_strategy_name(payload_dict, context)
        artifact = save_json(
            module=str(context.get("module") or category or "research"),
            artifact_type=f"{category}_capture",
            payload=document,
            symbol=symbol,
            theme=context.get("theme"),
            tags=["v24.5_capture", category, "research_only"],
            repo_root=repo,
            ingest=ingest_artifact,
        )

        typed_rows: dict[str, str] = {}
        backend = _select_backend(preferred_backend)

        try:
            from services.quant_schema.repository import (
                insert_experiment_run,
                insert_strategy_run,
                insert_backtest_run,
                insert_walk_forward_run,
                insert_universe_run,
                insert_data_quality_event,
            )

            metrics = extract_metrics(payload_dict)
            with _db_connect(repo, backend) as db:
                exp_id = insert_experiment_run(
                    db,
                    experiment_id=f"exp_{artifact.artifact_id}",
                    module=str(context.get("module") or category),
                    experiment_name=str(context.get("experiment_name") or f"{category}_capture"),
                    status="captured",
                    config={"context": context},
                    artifact_id=artifact.artifact_id,
                    commit=False,
                )
                typed_rows["experiment_runs"] = exp_id

                if category in {"strategy", "auto_lab", "backtest", "walk_forward"}:
                    strat_id = insert_strategy_run(
                        db,
                        strategy_run_id=f"strat_{artifact.artifact_id}",
                        experiment_id=exp_id,
                        artifact_id=artifact.artifact_id,
                        strategy_name=strategy_name,
                        strategy_family=str(context.get("strategy_family") or category),
                        symbol=symbol,
                        timeframe=metrics.get("timeframe"),
                        parameters=_safe_json(_first(payload_dict, ["parameters", "params", "config"]) or {}),
                        signal_count=_to_int(_first(payload_dict, ["signal_count", "signals"])),
                        status="captured",
                        commit=False,
                    )
                    typed_rows["strategy_runs"] = strat_id

                if category in {"backtest", "auto_lab"} and symbol:
                    bt_id = insert_backtest_run(
                        db,
                        backtest_run_id=f"bt_{artifact.artifact_id}",
                        strategy_run_id=typed_rows.get("strategy_runs"),
                        experiment_id=exp_id,
                        artifact_id=artifact.artifact_id,
                        symbol=symbol,
                        strategy_name=strategy_name,
                        timeframe=metrics.get("timeframe"),
                        start_date=metrics.get("start_date"),
                        end_date=metrics.get("end_date"),
                        initial_capital=metrics.get("initial_capital"),
                        ending_capital=metrics.get("ending_capital"),
                        total_return=metrics.get("total_return"),
                        cagr=metrics.get("cagr"),
                        sharpe=metrics.get("sharpe"),
                        sortino=metrics.get("sortino"),
                        max_drawdown=metrics.get("max_drawdown"),
                        win_rate=metrics.get("win_rate"),
                        profit_factor=metrics.get("profit_factor"),
                        trade_count=metrics.get("trade_count"),
                        turnover=metrics.get("turnover"),
                        fees=metrics.get("fees"),
                        slippage=metrics.get("slippage"),
                        status="captured",
                        metrics=_safe_json(payload_dict),
                        commit=False,
                    )
                    typed_rows["backtest_runs"] = bt_id

                if category == "walk_forward" and symbol:
                    wf_id = insert_walk_forward_run(
                        db,
                        walk_forward_run_id=f"wf_{artifact.artifact_id}",
                        experiment_id=exp_id,
                        artifact_id=artifact.artifact_id,
                        symbol=symbol,
                        strategy_name=strategy_name,
                        timeframe=metrics.get("timeframe"),
                        window_count=_to_int(_first(payload_dict, ["window_count", "windows"])),
                        avg_sharpe=_to_float(_first(payload_dict, ["avg_sharpe", "average_sharpe"])),
                        median_sharpe=_to_float(_first(payload_dict, ["median_sharpe"])),
                        avg_return=_to_float(_first(payload_dict, ["avg_return", "average_return"])),
                        max_drawdown=metrics.get("max_drawdown"),
                        pass_rate=_to_float(_first(payload_dict, ["pass_rate"])),
                        stability_score=_to_float(_first(payload_dict, ["stability_score"])),
                        status="captured",
                        metrics=_safe_json(payload_dict),
                        commit=False,
                    )
                    typed_rows["walk_forward_runs"] = wf_id

                if category == "universe":
                    symbols = _first(payload_dict, ["symbols", "selected_symbols", "suggested_symbols"]) or []
                    if isinstance(symbols, str):
                        symbols = [s.strip().upper() for s in re.split(r"[,\\s]+", symbols) if s.strip()]
                    if isinstance(symbols, list):
                        uni_id = insert_universe_run(
                            db,
                            universe_run_id=f"uni_{artifact.artifact_id}",
                            experiment_id=exp_id,
                            artifact_id=artifact.artifact_id,
                            universe_name=str(context.get("universe_name") or _first(payload_dict, ["universe_name"]) or "captured_universe"),
                            theme=str(context.get("theme") or _first(payload_dict, ["theme"]) or ""),
                            symbols=[str(s) for s in symbols],
                            selected_count=len(symbols),
                            ranking=_safe_json(_first(payload_dict, ["ranking", "rankings"]) or []),
                            status="captured",
                            commit=False,
                        )
                        typed_rows["universe_runs"] = uni_id

                if category == "data_quality":
                    dq_id = insert_data_quality_event(
                        db,
                        event_id=f"dq_{artifact.artifact_id}",
                        artifact_id=artifact.artifact_id,
                        symbol=symbol,
                        dataset_name=str(context.get("dataset_name") or "captured_dataset"),
                        severity=str(context.get("severity") or "info"),
                        event_type=str(context.get("event_type") or "captured_event"),
                        message=str(context.get("message") or "Captured data quality event."),
                        details=_safe_json(payload_dict),
                        commit=False,
                    )
                    typed_rows["data_quality_events"] = dq_id

                if hasattr(db, "commit"):
                    db.commit()
                elif hasattr(db, "conn"):
                    db.conn.commit()

            return CaptureResult(
                status="captured",
                category=category,
                artifact_id=artifact.artifact_id,
                artifact_path=artifact.path,
                quant_backend=backend,
                typed_rows=typed_rows,
            )
        except Exception as typed_exc:
            return CaptureResult(
                status="artifact_only",
                category=category,
                artifact_id=artifact.artifact_id,
                artifact_path=artifact.path,
                quant_backend=backend,
                typed_rows=typed_rows,
                error=f"typed_schema_error: {type(typed_exc).__name__}: {typed_exc}",
            )

    except Exception as exc:
        return CaptureResult(
            status="failed",
            category=category,
            error=f"{type(exc).__name__}: {exc}",
        )


def capture_research_result(
    *,
    category: str,
    payload: Any,
    context: dict[str, Any] | None = None,
    repo_root: str | Path | None = None,
    preferred_backend: str | None = None,
    ingest_artifact: bool | None = True,
) -> CaptureResult:
    """Guarded public capture function.

    Prevents recursive capture loops. Original implementation is kept as
    _capture_research_result_impl().
    """
    global _CAPTURE_ACTIVE
    if _CAPTURE_ACTIVE:
        return CaptureResult(
            status="skipped_reentrant",
            category=category,
            error="capture skipped because another capture is already active",
        )

    _CAPTURE_ACTIVE = True
    try:
        return _capture_research_result_impl(
            category=category,
            payload=payload,
            context=context,
            repo_root=repo_root,
            preferred_backend=preferred_backend,
            ingest_artifact=ingest_artifact,
        )
    except RecursionError as exc:
        return CaptureResult(
            status="skipped_recursion",
            category=category,
            error=f"RecursionError: {exc}",
        )
    finally:
        _CAPTURE_ACTIVE = False

def capture_backtest_result(payload: Any, context: dict[str, Any] | None = None, **kwargs: Any) -> CaptureResult:
    return capture_research_result(category="backtest", payload=payload, context=context, **kwargs)


def capture_auto_lab_result(payload: Any, context: dict[str, Any] | None = None, **kwargs: Any) -> CaptureResult:
    return capture_research_result(category="auto_lab", payload=payload, context=context, **kwargs)


def capture_walk_forward_result(payload: Any, context: dict[str, Any] | None = None, **kwargs: Any) -> CaptureResult:
    return capture_research_result(category="walk_forward", payload=payload, context=context, **kwargs)


def capture_universe_result(payload: Any, context: dict[str, Any] | None = None, **kwargs: Any) -> CaptureResult:
    return capture_research_result(category="universe", payload=payload, context=context, **kwargs)


def capture_strategy_result(payload: Any, context: dict[str, Any] | None = None, **kwargs: Any) -> CaptureResult:
    return capture_research_result(category="strategy", payload=payload, context=context, **kwargs)
