from .source_registry import ResearchSource, TrustedSourceRegistry, build_default_source_registry
from .research_brief import ResearchBrief, ResearchBriefBuilder
from .research_context import ResearchContextPack, ResearchContextBuilder

__all__ = [
    "ResearchSource",
    "TrustedSourceRegistry",
    "build_default_source_registry",
    "ResearchBrief",
    "ResearchBriefBuilder",
    "ResearchContextPack",
    "ResearchContextBuilder",
]
try:
    from services.research.query_planner import PlannedQuery, plan_query
    from services.research.search_links import ResearchLink, build_source_search_links
    from services.research.result_validator import ValidationResult, validate_research_url
except Exception:
    pass
try:
    from services.research.source_relevance import QueryProfile, SourceRoute, classify_query, route_sources_for_query
except Exception:
    pass

# Patch 30 — FRED connector exports
try:
    from .fred_connector import (
        FredObservationSummary,
        FredSeriesCandidate,
        build_fred_research_brief,
        curated_fred_candidates,
        format_fred_brief_markdown,
        get_fred_api_key,
        search_fred_series,
        summarize_fred_series,
    )
except Exception:
    pass
# Patch 31 optional exports.
try:
    from .fred_newsroom_adapter import build_fred_newsroom_items, extend_results_with_fred
except Exception:
    build_fred_newsroom_items = None
    extend_results_with_fred = None
# Patch 31b result hygiene helpers
try:
    from .result_hygiene import clean_newsroom_results, summarize_hygiene
except Exception:  # pragma: no cover - optional package surface only
    pass

try:
    from .brief_ai_handoff import brief_to_strategy_ai_context, default_newsroom_ai_prompt
except Exception:
    brief_to_strategy_ai_context = None
    default_newsroom_ai_prompt = None
