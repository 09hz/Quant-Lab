from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

try:
    from services.research.source_quality import grade_url
except Exception:
    grade_url = None


TRUSTED_SYNTHETIC_KINDS = {
    "fred-hydrated-official-data",
    "fred_hydrated_official_data",
    "official_data_card",
    "hydrated_fred",
}


@dataclass
class GateDecision:
    keep: bool
    score: int
    grade: str
    reason: str
    url: str = ""
    flags: list[str] = field(default_factory=list)


def _extract_url(item: Any) -> str:
    if not isinstance(item, dict):
        return ""

    for key in ("url", "link", "href", "source_url", "canonical_url", "source_link"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    source = item.get("source")
    if isinstance(source, dict):
        for key in ("url", "link", "href", "source_url", "canonical_url"):
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        for key in ("url", "link", "href", "source_url", "canonical_url"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    return ""


def _is_hydrated_official(item: Any) -> bool:
    if not isinstance(item, dict):
        return False

    kind = str(item.get("kind") or item.get("type") or "").strip().lower()
    if kind in TRUSTED_SYNTHETIC_KINDS:
        return True

    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        if metadata.get("hydrated") is True and str(metadata.get("series_id") or "").strip():
            return True

    return False


def decide_evidence_item(item: Any, *, min_score: int = 70) -> GateDecision:
    if _is_hydrated_official(item):
        return GateDecision(
            keep=True,
            score=100,
            grade="trusted_hydrated_official_data",
            reason="Hydrated official data card with structured series metadata.",
        )

    url = _extract_url(item)
    if not url:
        return GateDecision(
            keep=True,
            score=75,
            grade="no_url_structured_or_text_evidence",
            reason="No URL found; kept because it may be structured internal evidence.",
        )

    if grade_url is None:
        return GateDecision(
            keep=True,
            score=70,
            grade="quality_checker_unavailable",
            reason="source_quality.grade_url unavailable; evidence kept.",
            url=url,
        )

    quality = grade_url(url)
    flags = list(getattr(quality, "flags", []) or [])
    keep = int(quality.score) >= int(min_score)
    reason = "Specific enough for AI evidence." if keep else "Weak landing/search URL blocked from AI evidence."

    return GateDecision(
        keep=keep,
        score=int(quality.score),
        grade=str(quality.grade),
        reason=reason,
        url=url,
        flags=flags,
    )


def filter_ai_evidence_items(items: list[Any], *, min_score: int = 70) -> tuple[list[Any], list[dict[str, Any]]]:
    kept: list[Any] = []
    blocked: list[dict[str, Any]] = []

    for item in items or []:
        decision = decide_evidence_item(item, min_score=min_score)
        if decision.keep:
            kept.append(item)
        else:
            title = ""
            source = ""
            if isinstance(item, dict):
                title = str(item.get("title") or item.get("headline") or item.get("name") or "")[:240]
                source = str(item.get("source") or item.get("provider") or "")[:120]
            blocked.append(
                {
                    "title": title,
                    "source": source,
                    "url": decision.url,
                    "score": decision.score,
                    "grade": decision.grade,
                    "flags": decision.flags,
                    "reason": decision.reason,
                }
            )

    return kept, blocked


def quality_gate_markdown(blocked: list[dict[str, Any]]) -> str:
    if not blocked:
        return "Newsroom AI evidence quality gate: no weak landing/search URLs were blocked."

    lines = [
        f"Newsroom AI evidence quality gate: blocked {len(blocked)} weak landing/search URL(s) from the AI evidence packet.",
        "",
        "| Score | Grade | Reason | URL |",
        "|---:|---|---|---|",
    ]

    for row in blocked[:25]:
        url = str(row.get("url") or "")
        if len(url) > 120:
            url = url[:117] + "..."
        lines.append(
            f"| {row.get('score', '')} | {row.get('grade', '')} | {row.get('reason', '')} | {url} |"
        )

    return "\n".join(lines)
