from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .context_builder import build_evidence_packet
from .evidence_schema import EvidencePacket, EvidenceRow
from .research_plan import build_research_plan
from .source_policy import classify_source


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _lower_blob(item: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("source", "provider", "kind", "type", "title", "headline", "summary", "url", "source_url", "link"):
        value = item.get(key)
        if value not in (None, ""):
            parts.append(str(value))
    return " ".join(parts).lower()


def _parse_number(value: Any) -> Any:
    if value in (None, ""):
        return ""
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip().replace(",", "").replace("$", "")
    if not text:
        return ""
    try:
        if re.fullmatch(r"[-+]?\d+", text):
            return int(text)
        return float(text)
    except Exception:
        return value


def _parse_series_id_from_item(item: dict[str, Any]) -> str:
    for key in ("series_id", "series", "id"):
        value = _as_text(item.get(key))
        if value and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{2,30}", value):
            if not value.lower().startswith("brief"):
                return value.upper()

    url = _as_text(item.get("url") or item.get("source_url") or item.get("link"))
    for pattern in (r"/series/([A-Za-z][A-Za-z0-9_]{2,30})", r"/timeseries/([A-Za-z][A-Za-z0-9_]{2,30})"):
        match = re.search(pattern, url)
        if match:
            return match.group(1).upper()

    title = _as_text(item.get("title") or item.get("headline"))
    match = re.search(r"\(([A-Za-z][A-Za-z0-9_]{2,30})\)", title)
    if match:
        return match.group(1).upper()

    summary = _as_text(item.get("summary"))
    match = re.search(r"\b(?:for|series)\s+([A-Za-z][A-Za-z0-9_]{2,30})\b", summary)
    if match:
        return match.group(1).upper()

    return ""


def _parse_latest_prior_from_summary(summary: str) -> dict[str, Any]:
    values: dict[str, Any] = {}
    text = _as_text(summary)
    if not text:
        return values

    latest = re.search(
        r"Latest\s+(?:FRED|BLS)\s+value\s+for\s+([A-Za-z][A-Za-z0-9_]{2,30})\s*:\s*([-+]?\$?[\d,]+(?:\.\d+)?)\s+on\s+(\d{4}-\d{2}-\d{2})",
        text,
        flags=re.IGNORECASE,
    )
    if latest:
        values["series_id"] = latest.group(1).upper()
        values["latest_value"] = _parse_number(latest.group(2))
        values["latest_date"] = latest.group(3)

    unit_freq = re.search(r"\(([^()]+?),\s*([^()]+?)\)\.?\s*(?:Prior value|$)", text, flags=re.IGNORECASE)
    if unit_freq:
        values["unit"] = unit_freq.group(1).strip()
        values["frequency"] = unit_freq.group(2).strip()

    prior = re.search(r"Prior\s+value\s*:\s*([-+]?\$?[\d,]+(?:\.\d+)?)\s+on\s+(\d{4}-\d{2}-\d{2})", text, flags=re.IGNORECASE)
    if prior:
        values["previous_value"] = _parse_number(prior.group(1))
        values["previous_date"] = prior.group(2)

    change = re.search(r"change\s+vs\s+prior\s*:\s*([-+]?\$?[\d,]+(?:\.\d+)?)", text, flags=re.IGNORECASE)
    if change:
        values["change_vs_prior"] = _parse_number(change.group(1))

    return values


def _pick_from_pools(item: dict[str, Any], *names: str) -> Any:
    pools: list[dict[str, Any]] = [item]
    for key in ("sec_fact", "fact", "data", "metadata", "raw", "extra"):
        value = item.get(key)
        if isinstance(value, dict):
            pools.append(value)

    for pool in pools:
        for name in names:
            if name in pool and pool.get(name) not in (None, ""):
                return pool.get(name)
    return ""


def detect_legacy_source_family(item: dict[str, Any]) -> str:
    blob = _lower_blob(item)
    if "companyfacts" in blob or "sec" in blob or "edgar" in blob:
        return "SEC"
    if "fred" in blob or "stlouisfed.org" in blob:
        return "FRED"
    if "bls" in blob or "data.bls.gov" in blob or "timeseries/" in blob:
        return "BLS"
    if "bea" in blob or "apps.bea.gov" in blob or "bea.gov" in blob:
        return "BEA"
    if "federal reserve" in blob:
        return "Federal Reserve"
    if "treasury" in blob:
        return "Treasury"
    return _as_text(item.get("source") or item.get("provider") or "unknown")


def legacy_newsroom_item_to_evidence_row(item: dict[str, Any], index: int | None = None) -> EvidenceRow:
    if not isinstance(item, dict):
        raise TypeError("legacy_newsroom_item_to_evidence_row expected a dict")

    source_family = detect_legacy_source_family(item)
    policy = classify_source(source_family)
    kind = _as_text(item.get("kind") or item.get("type") or "research_link")
    title = _as_text(item.get("title") or item.get("headline") or f"{source_family} evidence row")
    summary = _as_text(item.get("summary"))
    url = _as_text(item.get("url") or item.get("source_url") or item.get("link"))
    confidence = _as_text(item.get("confidence") or item.get("validity") or "unknown")

    values: dict[str, Any] = {}
    metadata: dict[str, Any] = {
        "legacy_index": index,
        "legacy_source": item.get("source"),
        "legacy_kind": kind,
    }

    if source_family == "SEC":
        values.update(
            {
                "ticker": _pick_from_pools(item, "ticker", "symbol"),
                "entity": _pick_from_pools(item, "entity", "entityName", "company", "company_name", "issuer"),
                "metric": _pick_from_pools(item, "metric", "label", "fact_label", "name"),
                "value": _parse_number(_pick_from_pools(item, "latest_value", "value", "val", "latest", "amount")),
                "unit": _pick_from_pools(item, "unit", "units", "uom"),
                "period_end": _pick_from_pools(item, "period_end", "end", "period", "date"),
                "filed": _pick_from_pools(item, "filed", "filed_date", "filing_date"),
                "form": _pick_from_pools(item, "form", "filing_form"),
                "accession": _pick_from_pools(item, "accession", "accn", "accession_number"),
                "concept": _pick_from_pools(item, "concept", "concept_name", "xbrl_concept", "tag"),
                "cik": _pick_from_pools(item, "cik", "CIK"),
            }
        )
        evidence_type = "sec_companyfacts"
        row_title = f"{values.get('ticker') or 'SEC'} {values.get('metric') or title}".strip()

    elif source_family in {"FRED", "BLS"}:
        values.update(_parse_latest_prior_from_summary(summary))
        series_id = _parse_series_id_from_item(item)
        if series_id and not values.get("series_id"):
            values["series_id"] = series_id
        evidence_type = "macro_timeseries" if kind in {"fred-data", "bls-data"} or values.get("latest_value") not in (None, "") else "metadata_only_source_link"
        row_title = title
        if evidence_type == "metadata_only_source_link":
            metadata["evidence_status"] = f"metadata-only {source_family} source link; numeric latest/prior values were not read or provided"
        else:
            metadata["evidence_status"] = f"readable {source_family} data row"

    elif source_family == "BEA":
        evidence_type = kind if kind != "research_link" else "bea_placeholder_or_legacy_row"
        row_title = title
        metadata["bea_placeholder_supported"] = True
        if not url:
            metadata["evidence_status"] = "BEA schema placeholder; adapter not connected in v19.1"

    else:
        evidence_type = kind
        row_title = title

    for key in (
        "latest_value", "previous_value", "latest_date", "previous_date", "change_vs_prior",
        "unit", "units", "frequency", "series_id", "metric", "period_end", "filed", "form",
        "accession", "concept", "ticker", "entity",
    ):
        if key in item and key not in values and item.get(key) not in (None, ""):
            values[key] = item.get(key)

    values = {key: value for key, value in values.items() if value not in (None, "")}
    metadata = {key: value for key, value in metadata.items() if value not in (None, "")}

    notes: list[str] = ["Converted from selected legacy Newsroom/Research Brief row."]
    if policy.source_quality in {"third_party_context_only", "unclassified_context_only"}:
        notes.append("Context-only source; cannot override official facts.")
    if source_family in {"SEC", "FRED", "BLS", "BEA"}:
        notes.append("Official-source family recognized by router bridge.")

    return EvidenceRow(
        source_family=source_family,
        source_quality=policy.source_quality,
        evidence_type=evidence_type,
        title=row_title,
        url=url,
        tool_name="legacy_newsroom_bridge",
        values=values,
        metadata=metadata,
        confidence=confidence,
        notes=notes,
    )


def legacy_brief_to_evidence_rows(brief: list[dict[str, Any]]) -> list[EvidenceRow]:
    rows: list[EvidenceRow] = []
    for idx, item in enumerate(brief or [], start=1):
        if not isinstance(item, dict):
            continue
        try:
            rows.append(legacy_newsroom_item_to_evidence_row(item, index=idx))
        except Exception as exc:
            rows.append(
                EvidenceRow(
                    source_family="legacy_bridge_error",
                    source_quality="error",
                    evidence_type="conversion_error",
                    title=f"Legacy row conversion failed at index {idx}",
                    confidence="error",
                    metadata={"legacy_index": idx, "error": str(exc)},
                    notes=["This row failed conversion and should be inspected."],
                )
            )
    return rows


def make_bea_placeholder_row(reason: str = "BEA adapter not connected in v19.1") -> EvidenceRow:
    return EvidenceRow(
        source_family="BEA",
        source_quality="official_authoritative",
        evidence_type="bea_placeholder",
        title="BEA placeholder evidence row",
        url="https://www.bea.gov/data",
        tool_name="legacy_newsroom_bridge",
        confidence="placeholder",
        values={},
        metadata={"evidence_status": reason, "bea_placeholder_supported": True},
        notes=["Schema placeholder only. No BEA network fetch is performed in v19.1."],
    )


def build_router_packet_from_legacy_brief(
    brief: list[dict[str, Any]],
    question: str = "Legacy Newsroom Research Brief",
    include_bea_placeholder: bool = False,
) -> EvidencePacket:
    rows = legacy_brief_to_evidence_rows(brief)
    if include_bea_placeholder and not any(row.source_family == "BEA" for row in rows):
        rows.append(make_bea_placeholder_row())
    plan = build_research_plan(question, third_party_context_allowed=True)
    return build_evidence_packet(question, plan=plan, rows=rows)


def write_router_packet_diagnostics_from_legacy_brief(
    brief: list[dict[str, Any]],
    output_dir: str | Path,
    question: str = "Legacy Newsroom Research Brief",
    include_bea_placeholder: bool = False,
) -> EvidencePacket:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    packet = build_router_packet_from_legacy_brief(
        brief,
        question=question,
        include_bea_placeholder=include_bea_placeholder,
    )

    packet_json = output_path / "router_last_evidence_packet.json"
    packet_md = output_path / "router_last_evidence_packet.md"
    chart_json = output_path / "router_last_chart_ready_data.json"
    status_json = output_path / "router_last_legacy_bridge_status.json"

    packet_json.write_text(json.dumps(packet.to_dict(), indent=2, default=str), encoding="utf-8")
    packet_md.write_text(packet.to_markdown() + "\n", encoding="utf-8")
    chart_json.write_text(json.dumps(packet.chart_ready_data, indent=2, default=str), encoding="utf-8")

    grouped = packet.rows_by_source()
    status = {
        "status": "ok",
        "row_count": len(packet.rows),
        "chart_ready_rows": len(packet.chart_ready_data),
        "source_counts": {source: len(rows) for source, rows in sorted(grouped.items())},
        "packet_json": str(packet_json),
        "packet_md": str(packet_md),
        "chart_json": str(chart_json),
        "include_bea_placeholder": include_bea_placeholder,
    }
    status_json.write_text(json.dumps(status, indent=2, default=str), encoding="utf-8")
    return packet
