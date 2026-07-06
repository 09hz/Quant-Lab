"""
AI Auto Lab Orchestrator foundation.

This package is intentionally separate from the existing research_autolab modules.
It provides a clean orchestration layer that can call existing strategy/backtest
engines through adapters.

Research/simulation only. No broker execution.
"""

from .models import (
    ExperimentGoal,
    StrategyCandidate,
    NormalizedBacktestResult,
    StrategyScorecard,
    ExperimentRun,
)
from .orchestrator import AutoLabOrchestrator
from .templates import starter_strategy_candidates

__all__ = [
    "ExperimentGoal",
    "StrategyCandidate",
    "NormalizedBacktestResult",
    "StrategyScorecard",
    "ExperimentRun",
    "AutoLabOrchestrator",
    "starter_strategy_candidates",
]
