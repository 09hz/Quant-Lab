"""Research Loop Orchestrator.

Simulation-only strategy/backtest improvement loop.
No broker calls. No live trading. No order placement.
"""

from .models import ResearchLoopConfig, StrategyCandidate, CandidateEvaluation, ResearchLoopResult
from .orchestrator import run_research_loop

__all__ = [
    "ResearchLoopConfig",
    "StrategyCandidate",
    "CandidateEvaluation",
    "ResearchLoopResult",
    "run_research_loop",
]
