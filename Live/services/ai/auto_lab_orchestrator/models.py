from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from typing import Any
import json


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def local_now_iso() -> str:
    """Return the current machine-local time with an explicit UTC offset."""
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def local_run_timestamp() -> str:
    """Return a filesystem-safe timestamp based on the user's local clock."""
    now = datetime.now().astimezone()
    offset = now.strftime("%z") or "+0000"
    safe_offset = ("p" if offset.startswith("+") else "m") + offset[1:]
    return now.strftime("%Y-%m-%dT%H%M%S") + safe_offset


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def to_plain_data(value: Any) -> Any:
    """Convert dataclasses / simple objects into JSON-safe plain data."""
    if is_dataclass(value):
        return {k: to_plain_data(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): to_plain_data(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_plain_data(v) for v in value]
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    if hasattr(value, "to_dict"):
        try:
            return to_plain_data(value.to_dict())
        except Exception:
            pass
    if hasattr(value, "__dict__") and not isinstance(value, type):
        try:
            return {k: to_plain_data(v) for k, v in vars(value).items() if not k.startswith("_")}
        except Exception:
            pass
    try:
        json.dumps(value)
        return value
    except Exception:
        return str(value)


@dataclass
class ExperimentGoal:
    question: str = "Find robust simulation-only strategy candidates."
    symbols: list[str] = field(default_factory=lambda: ["AMD"])
    timeframe: str = "1d"
    start: str = ""
    end: str = ""
    starting_cash: float = 12000.0
    target_equity: float = 24000.0
    max_drawdown_pct: float = 30.0
    min_trades: int = 3
    execution_mode: str = "next_open"
    commission_per_order: float = 0.0
    slippage_bps: float = 1.0
    max_runs: int = 10
    simulation_only: bool = True
    notes: str = ""

    def target_return_pct(self) -> float:
        if self.starting_cash <= 0 or self.target_equity <= self.starting_cash:
            return 0.0
        return ((self.target_equity / self.starting_cash) - 1.0) * 100.0

    def to_dict(self) -> dict[str, Any]:
        return to_plain_data(self)


@dataclass
class StrategyCandidate:
    candidate_id: str
    name: str
    family: str
    script: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    symbols: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    source: str = "template"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return to_plain_data(self)


@dataclass
class NormalizedBacktestResult:
    candidate_id: str
    symbol: str
    status: str
    engine: str
    metrics: dict[str, Any] = field(default_factory=dict)
    trades: list[dict[str, Any]] = field(default_factory=list)
    equity_curve: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    raw_summary: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status.lower() == "ok" and not self.errors

    def metric(self, *names: str, default: float = 0.0) -> float:
        for name in names:
            if name in self.metrics:
                return safe_float(self.metrics.get(name), default)
        return default

    def to_dict(self) -> dict[str, Any]:
        return to_plain_data(self)


@dataclass
class StrategyScorecard:
    candidate_id: str
    symbol: str
    total_score: float
    grade: str

    # Compatibility with v21.0.
    passed: bool = False

    # v21.1 split status labels.
    engine_pass: bool = False
    research_pass: bool = False
    objective_hit: bool = False
    objective_progress_pct: float = 0.0

    component_scores: dict[str, float] = field(default_factory=dict)
    fail_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    interpretation: str = ""
    retest_recommendation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return to_plain_data(self)


@dataclass
class ExperimentRun:
    run_id: str
    created_at: str
    goal: ExperimentGoal
    candidates: list[StrategyCandidate]
    results: list[NormalizedBacktestResult]
    scorecards: list[StrategyScorecard]
    summary: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return to_plain_data(self)
