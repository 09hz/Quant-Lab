from __future__ import annotations

import re
from typing import Any

from .models import HypothesisRecord, StrategyMemoryRecord, stable_hash, utc_now_iso
from .symbol_hygiene import clean_symbol_list


POSITIVE_TERMS = [
    "objective_hit",
    "research_pass",
    "partial_survival",
    "passed",
    "survived",
    "candidate",
]

NEGATIVE_TERMS = [
    "high_overfit_warning",
    "medium_overfit_warning",
    "weak_out_of_sample",
    "failed",
    "reject",
    "rejected",
    "overfit",
]

STRATEGY_FAMILY_PATTERNS: list[tuple[str, list[str]]] = [
    ("rsi_mean_reversion", ["rsi", "mean reversion", "crossunder", "crossover"]),
    ("trend_following", ["trend", "sma", "ema", "moving average", "breakout"]),
    ("macd_momentum", ["macd", "momentum"]),
    ("bollinger_reversion", ["bollinger", "band"]),
    ("volatility_breakout", ["atr", "volatility", "breakout"]),
    ("generic_signal_strategy", ["strategy", "signal", "buy", "sell"]),
]


def _clean_symbols(symbols: list[str] | None) -> list[str]:
    return clean_symbol_list(symbols)

def _clean_themes(themes: list[str] | None) -> list[str]:
    out: list[str] = []
    for raw in themes or []:
        value = " ".join(str(raw).strip().split())
        if value:
            out.append(value)
    return list(dict.fromkeys(out))


def _text_has_any(text: str, tokens: list[str]) -> bool:
    lowered = (text or "").lower()
    return any(token.lower() in lowered for token in tokens)


def _detect_strategy_family(text: str, metadata: dict[str, Any] | None = None) -> str:
    metadata = metadata or {}
    explicit = str(metadata.get("strategy_family") or "").strip()
    if explicit:
        return explicit

    lowered = (text or "").lower()
    for family, tokens in STRATEGY_FAMILY_PATTERNS:
        if any(token in lowered for token in tokens):
            return family
    return "unknown_strategy_family"


def _extract_strategy_name(text: str, metadata: dict[str, Any] | None = None) -> str:
    metadata = metadata or {}
    for key in ["strategy_name", "best_strategy", "script_name", "strategy"]:
        value = str(metadata.get(key) or "").strip()
        if value:
            return value[:120]

    patterns = [
        r"\b(seed_[A-Za-z0-9_]+)\b",
        r"\b([A-Za-z0-9_]+_rsi_[A-Za-z0-9_]+)\b",
        r"Strategy(?: candidate)?:\s*([A-Za-z0-9_\- ]{3,120})",
        r"strategy_name['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9_\- ]{3,120})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text or "", flags=re.IGNORECASE)
        if match:
            return " ".join(match.group(1).strip().split())[:120]

    family = _detect_strategy_family(text, metadata)
    if family != "unknown_strategy_family":
        return family
    return ""


def _extract_score(text: str, metadata: dict[str, Any] | None = None) -> float:
    metadata = metadata or {}
    for key in ["score", "test_score", "best_score", "final_score"]:
        try:
            if key in metadata and metadata[key] is not None:
                return float(metadata[key])
        except Exception:
            pass

    patterns = [
        r"test_score\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)",
        r"score\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)",
        r"Score\s*\|\s*([0-9]+(?:\.[0-9]+)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text or "")
        if match:
            try:
                return float(match.group(1))
            except Exception:
                pass
    return 0.0


def _strategy_status(text: str, source_type: str, metadata: dict[str, Any] | None = None) -> str:
    metadata = metadata or {}
    lowered = (text or "").lower()

    if str(metadata.get("objective_hit")).lower() == "true" or str(metadata.get("research_pass")).lower() == "true":
        return "candidate_needs_walk_forward" if "walk_forward" not in source_type else "validated_candidate"

    if "high_overfit_warning" in lowered or "weak_out_of_sample" in lowered:
        return "rejected_or_needs_rework"

    if "partial_survival" in lowered or "medium_overfit_warning" in lowered:
        return "partial_survival_needs_retest"

    if "walk_forward" in source_type:
        return "observed_walk_forward"

    if _text_has_any(text, POSITIVE_TERMS):
        return "candidate_needs_walk_forward"

    if _text_has_any(text, NEGATIVE_TERMS):
        return "needs_rework"

    return "observed"


def hypotheses_from_evidence(
    evidence_id: str,
    source_type: str,
    title: str,
    text: str,
    symbols: list[str] | None,
    themes: list[str] | None,
    metadata: dict[str, Any] | None = None,
) -> list[HypothesisRecord]:
    """Create persistent research hypotheses from evidence.

    These are research hypotheses only. They are not trading instructions.
    """
    metadata = metadata or {}
    now = utc_now_iso()
    clean_symbols = _clean_symbols(symbols)
    clean_themes = _clean_themes(themes)
    hypotheses: list[HypothesisRecord] = []

    if clean_symbols and clean_themes:
        primary_theme = clean_themes[0]
        top_symbols = clean_symbols[:10]
        title_text = f"Test {primary_theme} basket across {', '.join(top_symbols[:6])}"
        thesis = (
            f"Evidence `{title}` links {', '.join(top_symbols)} with `{primary_theme}`. "
            "A future Auto Lab cycle should test this as a basket, then require walk-forward validation "
            "before any user handoff."
        )
        hypotheses.append(
            HypothesisRecord(
                id=stable_hash(f"{primary_theme}|{','.join(top_symbols)}|basket_hypothesis", prefix="hyp_"),
                title=title_text,
                thesis=thesis,
                status="open",
                confidence=0.58 + min(0.25, 0.02 * len(top_symbols)),
                symbols=top_symbols,
                themes=clean_themes,
                evidence_ids=[evidence_id],
                created_at=now,
                updated_at=now,
                metadata={
                    "source_type": source_type,
                    "hypothesis_type": "theme_symbol_basket",
                    "research_only": True,
                },
            )
        )

    if "walk_forward" in source_type or "overfit" in (text or "").lower():
        status = "needs_retest"
        confidence = 0.62
        if "high_overfit_warning" in (text or "").lower() or "weak_out_of_sample" in (text or "").lower():
            status = "rejected_or_needs_rework"
            confidence = 0.72
        elif "partial_survival" in (text or "").lower():
            status = "partial_survival_needs_retest"
            confidence = 0.66

        hypotheses.append(
            HypothesisRecord(
                id=stable_hash(f"{evidence_id}|walk_forward_overfit_control", prefix="hyp_"),
                title="Use walk-forward result to control overfit risk",
                thesis=(
                    "The evidence includes walk-forward/overfit signals. The AI researcher should reduce confidence "
                    "in single-run in-sample wins and prefer strategies that survive out-of-sample across multiple symbols."
                ),
                status=status,
                confidence=confidence,
                symbols=clean_symbols,
                themes=clean_themes,
                evidence_ids=[evidence_id],
                created_at=now,
                updated_at=now,
                metadata={
                    "source_type": source_type,
                    "hypothesis_type": "validation_control",
                    "research_only": True,
                },
            )
        )

    if "symbol_discovery" in source_type and clean_symbols:
        hypotheses.append(
            HypothesisRecord(
                id=stable_hash(f"{','.join(clean_symbols)}|symbol_discovery_universe", prefix="hyp_"),
                title=f"Use discovered universe: {', '.join(clean_symbols[:8])}",
                thesis=(
                    f"Symbol discovery suggested `{', '.join(clean_symbols)}`. Auto Lab should test the full universe, "
                    "compare results by symbol, and avoid promoting a strategy based on one isolated winner."
                ),
                status="open",
                confidence=0.64,
                symbols=clean_symbols,
                themes=clean_themes,
                evidence_ids=[evidence_id],
                created_at=now,
                updated_at=now,
                metadata={
                    "source_type": source_type,
                    "hypothesis_type": "discovered_universe",
                    "research_only": True,
                },
            )
        )

    return hypotheses


def strategy_memory_from_text(
    evidence_id: str,
    source_type: str,
    title: str,
    text: str,
    symbols: list[str] | None,
    themes: list[str] | None,
    metadata: dict[str, Any] | None = None,
) -> list[StrategyMemoryRecord]:
    metadata = metadata or {}
    strategy_name = _extract_strategy_name(text, metadata)
    family = _detect_strategy_family(text, metadata)

    if not strategy_name and family == "unknown_strategy_family":
        return []

    now = utc_now_iso()
    clean_symbols = _clean_symbols(symbols)
    status = _strategy_status(text, source_type, metadata)
    score = _extract_score(text, metadata)

    if not strategy_name:
        strategy_name = family

    return [
        StrategyMemoryRecord(
            id=stable_hash(f"{strategy_name}|{family}|{source_type}", prefix="strat_"),
            strategy_name=strategy_name,
            strategy_family=family,
            status=status,
            score=score,
            symbols=clean_symbols,
            result_refs=[evidence_id],
            created_at=now,
            updated_at=now,
            metadata={
                "source_type": source_type,
                "title": title,
                "themes": _clean_themes(themes),
                "research_only": True,
            },
        )
    ]
