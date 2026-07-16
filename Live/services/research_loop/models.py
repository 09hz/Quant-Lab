from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any
import uuid


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def make_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@dataclass
class ResearchLoopConfig:
    theme: str = "AI infrastructure semiconductors"
    symbols: list[str] = field(default_factory=lambda: ["AMD", "NVDA", "SMH"])
    max_candidates: int = 10
    max_loops: int = 1
    min_trades: int = 10
    max_drawdown_limit: float = -0.20
    min_sharpe: float = 0.25
    backend: str = "sqlite"
    mode: str = "simulation_only"
    evaluation_mode: str = "hybrid_safe"
    timeframe: str = "1d"
    seed: str = "v24_9_0"
    repo_root: str | None = None

    def normalized_symbols(self) -> list[str]:
        out: list[str] = []
        for symbol in self.symbols:
            cleaned = str(symbol or "").strip().upper()
            if cleaned and cleaned not in out:
                out.append(cleaned)
        return out

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["symbols"] = self.normalized_symbols()
        return data


@dataclass
class StrategyCandidate:
    candidate_id: str
    strategy_name: str
    strategy_family: str
    hypothesis: str
    symbols: list[str]
    timeframe: str
    parameters: dict[str, Any]
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SymbolBacktestResult:
    symbol: str
    total_return: float
    sharpe: float
    max_drawdown: float
    win_rate: float
    trade_count: int
    profit_factor: float
    data_quality: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CandidateEvaluation:
    candidate: StrategyCandidate
    symbol_results: list[SymbolBacktestResult]
    aggregate_metrics: dict[str, Any]
    walk_forward_metrics: dict[str, Any]
    universe_metrics: dict[str, Any]
    score: float
    status: str
    rejection_reasons: list[str]
    warnings: list[str]
    evaluated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate": self.candidate.to_dict(),
            "symbol_results": [item.to_dict() for item in self.symbol_results],
            "aggregate_metrics": dict(self.aggregate_metrics),
            "walk_forward_metrics": dict(self.walk_forward_metrics),
            "universe_metrics": dict(self.universe_metrics),
            "score": self.score,
            "status": self.status,
            "rejection_reasons": list(self.rejection_reasons),
            "warnings": list(self.warnings),
            "evaluated_at": self.evaluated_at,
        }


@dataclass
class ResearchLoopResult:
    loop_id: str
    config: ResearchLoopConfig
    candidates: list[StrategyCandidate]
    evaluations: list[CandidateEvaluation]
    survivors: list[CandidateEvaluation]
    report_paths: dict[str, str]
    quant_persist_status: str
    feedback_path: str
    started_at: str
    finished_at: str
    status: str
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "loop_id": self.loop_id,
            "config": self.config.to_dict(),
            "candidates": [item.to_dict() for item in self.candidates],
            "evaluations": [item.to_dict() for item in self.evaluations],
            "survivors": [item.to_dict() for item in self.survivors],
            "report_paths": dict(self.report_paths),
            "quant_persist_status": self.quant_persist_status,
            "feedback_path": self.feedback_path,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "status": self.status,
            "errors": list(self.errors),
        }
