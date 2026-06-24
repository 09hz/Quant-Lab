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
from .strategy_language_reference import build_strategy_language_context, detect_app_language_violations
from services.ai.context_packet import prepare_strategy_ai_context, StrategyAIContextReport
from .strategy_grammar_guard import build_strategy_grammar_reference, validate_strategy_lab_script
