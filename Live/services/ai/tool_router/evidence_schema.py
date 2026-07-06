from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class EvidenceRow:
    source_family: str
    source_quality: str
    evidence_type: str
    title: str
    url: str = ""
    row_id: str = field(default_factory=lambda: f"evidence-{uuid4().hex[:12]}")
    tool_name: str = ""
    fetched_at: str = field(default_factory=utc_now_iso)
    values: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    confidence: str = "unknown"
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "row_id": self.row_id,
            "source_family": self.source_family,
            "source_quality": self.source_quality,
            "evidence_type": self.evidence_type,
            "title": self.title,
            "url": self.url,
            "tool_name": self.tool_name,
            "fetched_at": self.fetched_at,
            "values": dict(self.values),
            "metadata": dict(self.metadata),
            "confidence": self.confidence,
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EvidenceRow":
        return cls(
            row_id=str(payload.get("row_id") or f"evidence-{uuid4().hex[:12]}"),
            source_family=str(payload.get("source_family") or "unknown"),
            source_quality=str(payload.get("source_quality") or "unknown"),
            evidence_type=str(payload.get("evidence_type") or "unknown"),
            title=str(payload.get("title") or "Untitled evidence"),
            url=str(payload.get("url") or ""),
            tool_name=str(payload.get("tool_name") or ""),
            fetched_at=str(payload.get("fetched_at") or utc_now_iso()),
            values=dict(payload.get("values") or {}),
            metadata=dict(payload.get("metadata") or {}),
            confidence=str(payload.get("confidence") or "unknown"),
            notes=list(payload.get("notes") or []),
        )

    def numeric_value(self) -> Any:
        for key in ("latest_value", "value", "amount"):
            if key in self.values:
                return self.values[key]
        return None

    def to_markdown(self, index: int | None = None) -> str:
        prefix = f"{index}. " if index is not None else ""
        lines = [
            f"### {prefix}{self.source_family}: {self.title}",
            f"- Source quality: {self.source_quality}",
            f"- Evidence type: {self.evidence_type}",
            f"- Confidence: {self.confidence}",
        ]
        if self.url:
            lines.append(f"- URL: {self.url}")
        if self.fetched_at:
            lines.append(f"- Fetched at: {self.fetched_at}")
        for key, value in self.values.items():
            lines.append(f"- {key}: {value}")
        for key, value in self.metadata.items():
            if key not in self.values:
                lines.append(f"- {key}: {value}")
        if self.notes:
            lines.append("- Notes:")
            for note in self.notes:
                lines.append(f"  - {note}")
        return "\n".join(lines)


@dataclass
class EvidencePacket:
    question: str
    rows: list[EvidenceRow] = field(default_factory=list)
    plan: dict[str, Any] = field(default_factory=dict)
    markdown_summary: str = ""
    chart_ready_data: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now_iso)
    packet_id: str = field(default_factory=lambda: f"packet-{uuid4().hex[:12]}")

    def add_row(self, row: EvidenceRow) -> None:
        self.rows.append(row)

    def rows_by_source(self) -> dict[str, list[EvidenceRow]]:
        grouped: dict[str, list[EvidenceRow]] = {}
        for row in self.rows:
            grouped.setdefault(row.source_family, []).append(row)
        return grouped

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "question": self.question,
            "created_at": self.created_at,
            "plan": dict(self.plan),
            "rows": [row.to_dict() for row in self.rows],
            "markdown_summary": self.markdown_summary,
            "chart_ready_data": list(self.chart_ready_data),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EvidencePacket":
        packet = cls(
            packet_id=str(payload.get("packet_id") or f"packet-{uuid4().hex[:12]}"),
            question=str(payload.get("question") or ""),
            created_at=str(payload.get("created_at") or utc_now_iso()),
            plan=dict(payload.get("plan") or {}),
            markdown_summary=str(payload.get("markdown_summary") or ""),
            chart_ready_data=list(payload.get("chart_ready_data") or []),
        )
        packet.rows = [EvidenceRow.from_dict(row) for row in payload.get("rows") or []]
        return packet

    def to_markdown(self) -> str:
        lines = [
            "# Structured Evidence Packet",
            "",
            f"- Packet ID: {self.packet_id}",
            f"- Created at: {self.created_at}",
            f"- Question: {self.question}",
            f"- Row count: {len(self.rows)}",
            "",
            "## Source inventory",
        ]
        grouped = self.rows_by_source()
        if not grouped:
            lines.append("- No evidence rows yet.")
        else:
            for source, rows in sorted(grouped.items()):
                lines.append(f"- {source}: {len(rows)} row(s)")
        if self.markdown_summary:
            lines += ["", "## Summary", "", self.markdown_summary]
        lines += ["", "## Evidence Rows", ""]
        for idx, row in enumerate(self.rows, start=1):
            lines.append(row.to_markdown(idx))
            lines.append("")
        return "\n".join(lines).rstrip()
