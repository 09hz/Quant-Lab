from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib
import json
import os
import uuid

from .models import (
    ExperimentGoal,
    ExperimentRun,
    StrategyCandidate,
    local_run_timestamp,
    utc_now_iso,
)
from .scorecard import score_strategy_result
from .adapters import ToyBacktestAdapter
from .report_builder import write_run_bundle
from .safety import assert_no_live_broker_modules_loaded, assert_safe_output_path, assert_simulation_only


EXACT_CACHE_VERSION = "autolab_exact_v1"


def build_run_id(prefix: str = "autolab") -> str:
    return f"{prefix}_{local_run_timestamp()}_{uuid.uuid4().hex[:8]}"


def build_exact_result_cache_key(
    *,
    live_root: Path,
    kind: str,
    symbol: str,
    csv_path: Path,
    settings: dict[str, Any],
) -> str:
    digest = hashlib.sha256()
    digest.update(EXACT_CACHE_VERSION.encode("utf-8"))
    digest.update(str(kind).encode("utf-8"))
    digest.update(str(symbol).upper().encode("utf-8"))
    digest.update(json.dumps(settings, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8"))
    for path in (
        Path(csv_path),
        live_root / "core" / "StrategyEngine.py",
        live_root / "core" / "BackTestEngine.py",
        Path(__file__).resolve(),
        Path(__file__).resolve().with_name("mutator.py"),
        Path(__file__).resolve().with_name("seed_library.py"),
    ):
        digest.update(str(path.name).encode("utf-8"))
        if path.exists():
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
    return digest.hexdigest()


def load_exact_symbol_result(*, live_root: Path, kind: str, cache_key: str) -> dict | None:
    path = live_root / "data" / "auto_lab_result_cache" / kind / f"{cache_key}.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if payload.get("cache_version") != EXACT_CACHE_VERSION or payload.get("cache_key") != cache_key:
        return None
    result = payload.get("result")
    return dict(result) if isinstance(result, dict) else None


def save_exact_symbol_result(*, live_root: Path, kind: str, cache_key: str, result: dict) -> Path:
    cache_dir = live_root / "data" / "auto_lab_result_cache" / kind
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{cache_key}.json"
    temporary = cache_dir / f".{cache_key}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    temporary.write_text(
        json.dumps(
            {
                "cache_version": EXACT_CACHE_VERSION,
                "cache_key": cache_key,
                "result": result,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    temporary.replace(path)
    return path


class AutoLabOrchestrator:
    """
    Coordinates AI Auto Lab experiments.

    The orchestrator does not decide strategy performance by itself. It delegates:
    - engine adapter runs the strategy/backtest
    - deterministic scorecard judges the result
    - report builder records the run
    """

    def __init__(self, adapter: Any | None = None, live_root: Path | None = None, output_root: Path | None = None) -> None:
        self.adapter = adapter or ToyBacktestAdapter()
        self.live_root = live_root or Path(__file__).resolve().parents[3]
        self.output_root = output_root or (self.live_root / "data" / "auto_lab_runs")

    def run_experiment(
        self,
        goal: ExperimentGoal,
        candidates: list[StrategyCandidate],
        bars_by_symbol: dict[str, Any],
        run_id: str | None = None,
        write_artifacts: bool = True,
    ) -> ExperimentRun:
        assert_simulation_only(goal.simulation_only)
        assert_no_live_broker_modules_loaded()

        if not candidates:
            raise ValueError("No strategy candidates supplied.")

        run_id = run_id or build_run_id()
        run_dir = self.output_root / run_id
        assert_safe_output_path(run_dir, self.live_root)

        results = []
        scorecards = []

        for candidate in candidates:
            symbols = candidate.symbols or goal.symbols
            for symbol in symbols:
                bars = bars_by_symbol.get(symbol)
                result = self.adapter.run_candidate(candidate=candidate, bars=bars, goal=goal, symbol=symbol)
                scorecard = score_strategy_result(result, goal)
                results.append(result)
                scorecards.append(scorecard)

        best = max(scorecards, key=lambda sc: sc.total_score) if scorecards else None
        passed = [sc for sc in scorecards if sc.passed]
        summary = {
            "candidate_count": len(candidates),
            "result_count": len(results),
            "passed_count": len(passed),
            "best_candidate_id": best.candidate_id if best else "",
            "best_symbol": best.symbol if best else "",
            "best_score": best.total_score if best else 0.0,
            "adapter": getattr(self.adapter, "engine_name", self.adapter.__class__.__name__),
            "simulation_only": goal.simulation_only,
        }

        run = ExperimentRun(
            run_id=run_id,
            created_at=utc_now_iso(),
            goal=goal,
            candidates=candidates,
            results=results,
            scorecards=scorecards,
            summary=summary,
            artifacts={},
        )
        if write_artifacts:
            run.artifacts = write_run_bundle(run, run_dir)
        else:
            run.artifacts = {
                "run_json": str(run_dir / "experiment_run.json"),
                "results_json": str(run_dir / "results.json"),
                "scorecards_json": str(run_dir / "scorecards.json"),
                "report_md": str(run_dir / "report.md"),
            }
        return run
