from __future__ import annotations

from typing import Any

from .evidence_schema import EvidencePacket, EvidenceRow
from .research_plan import ResearchPlan


def build_chart_ready_data(rows: list[EvidenceRow]) -> list[dict[str, Any]]:
    chart_rows: list[dict[str, Any]] = []
    for row in rows:
        values = row.values or {}
        date = values.get("latest_date") or values.get("date") or values.get("period_end")
        value = values.get("latest_value") or values.get("value") or values.get("amount")
        if date is None or value is None:
            continue
        chart_rows.append(
            {
                "row_id": row.row_id,
                "source_family": row.source_family,
                "series_or_metric": values.get("series_id") or values.get("metric") or row.title,
                "date": date,
                "value": value,
                "unit": values.get("unit") or values.get("units"),
                "title": row.title,
                "url": row.url,
            }
        )
    return chart_rows


def build_markdown_summary(packet: EvidencePacket) -> str:
    grouped = packet.rows_by_source()
    lines = ["# Evidence Summary", ""]
    if not packet.rows:
        lines.append("No evidence rows have been attached yet.")
    else:
        lines.append("## Source counts")
        for source, rows in sorted(grouped.items()):
            lines.append(f"- {source}: {len(rows)} row(s)")
        lines.append("")
        lines.append("## Source quality")
        quality_counts: dict[str, int] = {}
        for row in packet.rows:
            quality_counts[row.source_quality] = quality_counts.get(row.source_quality, 0) + 1
        for quality, count in sorted(quality_counts.items()):
            lines.append(f"- {quality}: {count}")
    lines += [
        "",
        "## Guardrail reminder",
        "- Official data rows override third-party context.",
        "- Third-party context cannot override SEC/FRED/BLS/BEA/Fed/Treasury official facts.",
        "- This is research/advisory/simulation only; no broker orders or live trading execution.",
    ]
    return "\n".join(lines)


def build_evidence_packet(question: str, plan: ResearchPlan | None = None, rows: list[EvidenceRow] | None = None) -> EvidencePacket:
    packet = EvidencePacket(
        question=question,
        rows=list(rows or []),
        plan=plan.to_dict() if plan is not None else {},
    )
    packet.chart_ready_data = build_chart_ready_data(packet.rows)
    packet.markdown_summary = build_markdown_summary(packet)
    return packet


def rows_from_legacy_newsroom_items(items: list[dict[str, Any]]) -> list[EvidenceRow]:
    rows: list[EvidenceRow] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source") or "unknown")
        kind = str(item.get("kind") or item.get("type") or "research_link")
        title = str(item.get("title") or item.get("headline") or "Untitled")
        url = str(item.get("url") or item.get("source_url") or item.get("link") or "")
        confidence = str(item.get("confidence") or item.get("validity") or "unknown")
        values = {}
        metadata = {}
        for key, value in item.items():
            if key in {"latest_value", "previous_value", "latest_date", "previous_date", "change_vs_prior", "unit", "units", "series_id", "metric", "period_end", "filed", "form", "accession", "concept", "ticker", "entity"}:
                values[key] = value
            elif key not in {"title", "headline", "url", "source_url", "link", "source", "kind", "type", "confidence", "validity"}:
                metadata[key] = value
        rows.append(
            EvidenceRow(
                source_family=source,
                source_quality="legacy_newsroom_row",
                evidence_type=kind,
                title=title,
                url=url,
                confidence=confidence,
                values=values,
                metadata=metadata,
                notes=["Converted from legacy Newsroom item; v19 router foundation only."],
            )
        )
    return rows
