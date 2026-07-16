from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
import hashlib
import json
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_hash(value: str, prefix: str = "") -> str:
    digest = hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:24]
    return f"{prefix}{digest}" if prefix else digest


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def json_loads(value: str | None, default: Any = None) -> Any:
    if value is None or value == "":
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


@dataclass(frozen=True)
class EvidenceItem:
    id: str
    source_type: str
    source_path: str
    title: str
    summary: str
    content_hash: str
    observed_at: str
    ingested_at: str
    symbols: list[str] = field(default_factory=list)
    entities: list[dict[str, Any]] = field(default_factory=list)
    themes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EntityRecord:
    canonical_name: str
    entity_type: str
    symbol: str = ""
    aliases: list[str] = field(default_factory=list)
    first_seen_at: str = ""
    last_seen_at: str = ""
    source_count: int = 1
    confidence: float = 0.50
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RelationshipRecord:
    id: str
    source_entity: str
    target_entity: str
    relationship_type: str
    confidence: float = 0.50
    impact_score: float = 0.50
    recency_score: float = 1.00
    evidence_count: int = 1
    first_seen_at: str = ""
    last_seen_at: str = ""
    evidence_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HypothesisRecord:
    id: str
    title: str
    thesis: str
    status: str = "open"
    confidence: float = 0.50
    symbols: list[str] = field(default_factory=list)
    themes: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ResearchRunRecord:
    id: str
    run_type: str
    run_path: str
    title: str
    status: str = "observed"
    started_at: str = ""
    ended_at: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)
    symbols: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StrategyMemoryRecord:
    id: str
    strategy_name: str
    strategy_family: str
    status: str = "observed"
    score: float = 0.0
    symbols: list[str] = field(default_factory=list)
    result_refs: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
