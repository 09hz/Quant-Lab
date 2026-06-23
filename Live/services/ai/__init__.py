"""Advisory AI service facade."""

from services.ai.advisor import (
    AIAdvisorRequest,
    AIAdvisorResult,
    AIAdvisorService,
    ask_ai_advisor,
    build_ai_advisor_service,
)

__all__ = [
    "AIAdvisorRequest",
    "AIAdvisorResult",
    "AIAdvisorService",
    "ask_ai_advisor",
    "build_ai_advisor_service",
]

# Patch 24 export
try:
    from services.ai.current_strategy_context import (
        StrategyRuntimeContext,
        build_strategy_runtime_context,
        summarize_bars,
    )
except Exception:
    StrategyRuntimeContext = None
    build_strategy_runtime_context = None
    summarize_bars = None
