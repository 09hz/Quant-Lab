from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ResearchHypothesis:
    id: str
    label: str
    rationale: str
    symbols: list[str]
    strategy_family: str
    filters: list[str] = field(default_factory=list)
    invalidation_rules: list[str] = field(default_factory=list)
    evidence_series: list[str] = field(default_factory=list)
    risk_notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BacktestRequest:
    hypothesis_id: str
    symbol: str
    strategy_family: str
    timeframe: str = "1 day"
    start: str | None = None
    end: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    macro_filters: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BacktestResult:
    request: BacktestRequest
    metrics: dict[str, float]
    notes: list[str] = field(default_factory=list)
    passed_safety_checks: bool = True
