from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass
from typing import Any
import json


@dataclass
class GenerationInfo:
    generation: int
    parent_id: str = ""
    is_mutation: bool = False
    source: str = ""


def candidate_generation(candidate_or_dict: Any) -> GenerationInfo:
    if isinstance(candidate_or_dict, dict):
        source = str(candidate_or_dict.get("source") or "")
        candidate_id = str(candidate_or_dict.get("candidate_id") or "")
        params = dict(candidate_or_dict.get("parameters") or {})
    else:
        source = str(getattr(candidate_or_dict, "source", "") or "")
        candidate_id = str(getattr(candidate_or_dict, "candidate_id", "") or "")
        params = dict(getattr(candidate_or_dict, "parameters", {}) or {})

    try:
        gen = int(params.get("generation", 0) or 0)
    except Exception:
        gen = 0

    parent_id = str(params.get("parent_id") or "")
    is_mutation = False

    if source.startswith("mutation_of:"):
        is_mutation = True
        parent_id = parent_id or source[len("mutation_of:"):]
        if gen <= 0:
            gen = 1

    if "_to_" in candidate_id and any(token in candidate_id for token in ("fast_", "slow_", "rsi_", "thr_", "qty_")):
        is_mutation = True
        if gen <= 0:
            gen = 1

    return GenerationInfo(generation=gen, parent_id=parent_id, is_mutation=is_mutation, source=source)


def is_mutation_run(payload: dict) -> bool:
    goal = str(((payload.get("goal") or {}).get("question")) or "").lower()
    artifacts = payload.get("artifacts") or {}
    candidates = payload.get("candidates") or []
    if "mutation" in goal:
        return True
    if "mutation_report_md" in artifacts or "mutation_results_json" in artifacts:
        return True
    return any(candidate_generation(c).is_mutation for c in candidates if isinstance(c, dict))


def is_core_engine_research_pass_run(payload: dict) -> bool:
    summary = payload.get("summary") or {}
    if "core_strategy_backtest_adapter" not in str(summary.get("adapter") or ""):
        return False
    scorecards = payload.get("scorecards") or []
    return any(
        bool(sc.get("engine_pass")) and bool(sc.get("research_pass"))
        for sc in scorecards
        if isinstance(sc, dict)
    )


def run_id_from_dir(run_dir: Path) -> str:
    return run_dir.name


def find_latest_parent_run_id(
    live_root: Path,
    allow_chained_mutations: bool = False,
) -> tuple[str, Path | None, dict]:
    runs_dir = live_root / "data" / "auto_lab_runs"
    if not runs_dir.exists():
        return "", None, {}

    for run_dir in sorted([p for p in runs_dir.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True):
        payload_path = run_dir / "experiment_run.json"
        if not payload_path.exists():
            continue
        try:
            payload = json.loads(payload_path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue

        if not is_core_engine_research_pass_run(payload):
            continue

        if not allow_chained_mutations and is_mutation_run(payload):
            continue

        return run_id_from_dir(run_dir), run_dir, payload

    return "", None, {}
