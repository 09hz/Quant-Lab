from __future__ import annotations

import re
from typing import Any

from .symbol_hygiene import NOISE_SYMBOLS, requested_theme_symbol_multiplier


THEME_ALIASES: dict[str, set[str]] = {
    "AI infrastructure": {
        "ai infrastructure",
        "artificial intelligence",
        "accelerator",
        "accelerators",
        "gpu",
        "gpus",
        "data center",
        "datacenter",
        "compute",
        "inference",
        "training",
    },
    "Semiconductors": {
        "semiconductor",
        "semiconductors",
        "chip",
        "chips",
        "foundry",
        "lithography",
        "wafer",
        "fab",
        "fabs",
    },
    "Cloud platforms": {
        "cloud",
        "azure",
        "aws",
        "gcp",
        "hyperscaler",
        "hyperscalers",
        "platform",
    },
    "Consumer discretionary": {
        "consumer discretionary",
        "consumer",
        "retail",
        "ev",
        "electric vehicle",
        "autos",
    },
    "Interest rates": {
        "interest rates",
        "rates",
        "fed",
        "federal reserve",
        "inflation",
        "treasury",
        "yield",
    },
    "Cybersecurity": {
        "cybersecurity",
        "cyber",
        "security",
        "zero trust",
        "ransomware",
    },
    "Energy": {
        "energy",
        "oil",
        "gas",
        "crude",
        "opec",
    },
    "Healthcare": {
        "healthcare",
        "health",
        "pharma",
        "biotech",
        "drug",
    },
    "Defense": {
        "defense",
        "aerospace",
        "geopolitical",
        "missile",
    },
}


def _norm(value: Any) -> str:
    return " ".join(str(value or "").lower().replace("_", " ").replace("-", " ").split())


def _flatten_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        parts = []
        for item in value.values():
            parts.append(_flatten_text(item))
        return " ".join(parts)
    if isinstance(value, list):
        return " ".join(_flatten_text(item) for item in value)
    return str(value)


def requested_theme_terms(requested_theme: str) -> set[str]:
    text = _norm(requested_theme)
    terms: set[str] = set()

    for canonical, aliases in THEME_ALIASES.items():
        canonical_norm = _norm(canonical)
        if canonical_norm in text or any(_norm(alias) in text for alias in aliases):
            terms.add(canonical_norm)
            terms.update(_norm(alias) for alias in aliases)

    for token in re.findall(r"[a-zA-Z][a-zA-Z0-9]{2,}", text):
        if token not in {"and", "the", "for", "with", "from", "into"}:
            terms.add(token)

    return {term for term in terms if term}


def theme_match_score(row: dict[str, Any], requested_theme: str) -> float:
    terms = requested_theme_terms(requested_theme)
    if not terms:
        return 0.0

    haystack = _norm(_flatten_text(row))
    if not haystack:
        return 0.0

    score = 0.0
    for term in terms:
        if not term:
            continue
        if term in haystack:
            score += 2.0 if " " in term else 1.0

    # Direct metadata/theme matches are especially important.
    for key in ["themes", "research_theme_candidates"]:
        values = row.get(key, [])
        if isinstance(values, str):
            values = [values]
        for value in values or []:
            value_norm = _norm(value)
            for term in terms:
                if term in value_norm or value_norm in term:
                    score += 3.0

    # Theme symbol multiplier gives relevant symbols a smaller but useful boost.
    symbols = row.get("symbols") or row.get("suggested_symbols") or []
    if isinstance(symbols, str):
        symbols = re.split(r"[,;\s]+", symbols)
    for symbol in symbols or []:
        mult = requested_theme_symbol_multiplier(str(symbol), requested_theme)
        if mult > 1.0:
            score += min(2.0, mult - 1.0)

    return round(score, 4)


def rank_rows_by_theme(
    rows: list[dict[str, Any]],
    requested_theme: str,
    fallback_score_keys: list[str] | None = None,
) -> list[dict[str, Any]]:
    fallback_score_keys = fallback_score_keys or ["confidence", "score", "evidence_count", "source_count"]
    ranked: list[dict[str, Any]] = []

    for idx, row in enumerate(rows):
        item = dict(row)
        match_score = theme_match_score(item, requested_theme)
        fallback_score = 0.0
        for key in fallback_score_keys:
            try:
                fallback_score += float(item.get(key) or 0.0)
            except Exception:
                pass

        status = str(item.get("status") or "").lower()
        penalty = 0.0
        if "rejected" in status:
            penalty += 1.0
        if "rework" in status:
            penalty += 0.5

        item["theme_match_score"] = match_score
        item["_theme_rank_score"] = (match_score * 10.0) + fallback_score - penalty - (idx * 0.0001)
        ranked.append(item)

    ranked.sort(key=lambda row: (-float(row.get("_theme_rank_score") or 0.0), str(row.get("title") or row.get("source_entity") or "")))
    for row in ranked:
        row.pop("_theme_rank_score", None)
    return ranked


def build_theme_match_summary(
    requested_theme: str,
    ranked_symbols: list[dict[str, Any]],
    hypotheses: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
) -> dict[str, Any]:
    terms = sorted(requested_theme_terms(requested_theme))
    top_hypothesis_score = float(hypotheses[0].get("theme_match_score") or 0.0) if hypotheses else 0.0
    top_relationship_score = float(relationships[0].get("theme_match_score") or 0.0) if relationships else 0.0

    relevant_symbols = []
    off_theme_symbols = []
    for row in ranked_symbols:
        symbol = str(row.get("symbol") or "").upper()
        if not symbol:
            continue
        if requested_theme_symbol_multiplier(symbol, requested_theme) > 1.0:
            relevant_symbols.append(symbol)
        else:
            off_theme_symbols.append(symbol)

    return {
        "requested_theme": requested_theme,
        "matched_terms": terms[:30],
        "top_hypothesis_theme_match_score": top_hypothesis_score,
        "top_relationship_theme_match_score": top_relationship_score,
        "theme_relevant_symbols": relevant_symbols,
        "off_theme_symbols": off_theme_symbols,
    }


def packet_quality_score_and_warnings(packet: dict[str, Any]) -> tuple[int, list[str]]:
    warnings: list[str] = []
    score = 100

    suggested = [str(item).upper() for item in packet.get("suggested_symbols", [])]
    if not suggested:
        warnings.append("no_suggested_symbols")
        score -= 30

    noisy = sorted(set(suggested).intersection(NOISE_SYMBOLS))
    if noisy:
        warnings.append("noise_symbols_present:" + ",".join(noisy))
        score -= 30

    hypotheses = packet.get("hypotheses", [])
    if not hypotheses:
        warnings.append("no_hypotheses")
        score -= 20
    else:
        top_score = float(hypotheses[0].get("theme_match_score") or 0.0)
        if packet.get("requested_theme") and top_score <= 0:
            warnings.append("top_hypothesis_not_theme_matched")
            score -= 20

    relationships = packet.get("top_relationships", [])
    if not relationships:
        warnings.append("no_relationships")
        score -= 15

    theme_summary = packet.get("theme_match_summary", {})
    relevant = theme_summary.get("theme_relevant_symbols") or []
    if packet.get("requested_theme") and len(relevant) < max(1, min(3, len(suggested))):
        warnings.append("few_theme_relevant_symbols")
        score -= 10

    if "walk_forward_validation" not in packet.get("validation_required", []):
        warnings.append("missing_walk_forward_validation_requirement")
        score -= 10

    return max(0, min(100, int(score))), warnings
