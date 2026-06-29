from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse


OFFICIAL_DOMAINS = {
    "fred.stlouisfed.org",
    "api.stlouisfed.org",
    "bea.gov",
    "apps.bea.gov",
    "bls.gov",
    "sec.gov",
    "federalreserve.gov",
    "treasury.gov",
    "fiscaldata.treasury.gov",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _clean_text(value: Any, *, max_len: int = 1200) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = " ".join(text.split())
    if len(text) > max_len:
        return text[: max_len - 1].rstrip() + "…"
    return text


def _first_present(mapping: dict[str, Any], keys: tuple[str, ...], default: Any = "") -> Any:
    for key in keys:
        if key in mapping and mapping.get(key) not in (None, ""):
            return mapping.get(key)
    return default


def _domain_from_url(url: str) -> str:
    try:
        host = urlparse(str(url or "")).netloc.lower().strip()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def _source_type_from_item(item: dict[str, Any], domain: str) -> str:
    raw = str(
        _first_present(
            item,
            ("source_type", "type", "category", "publisher_type"),
            "",
        )
        or ""
    ).lower()

    if "official" in raw or "government" in raw:
        return "official"
    if "filing" in raw or domain.endswith("sec.gov"):
        return "filing"
    if domain in OFFICIAL_DOMAINS or domain.endswith(".gov"):
        return "official"
    if "news" in raw or "article" in raw:
        return "news"
    return "source"


def _validity_label(source_type: str, domain: str, item: dict[str, Any]) -> str:
    confidence = str(_first_present(item, ("confidence", "confidence_label"), "") or "").lower()
    reliability = str(_first_present(item, ("reliability", "reliability_label"), "") or "").lower()

    if source_type in {"official", "filing"}:
        return "high"
    if "high" in confidence or "high" in reliability:
        return "high"
    if "low" in confidence or "low" in reliability:
        return "low"
    if domain:
        return "medium"
    return "unknown"


def _extract_list_candidates(payload: Any) -> list[Any]:
    if payload is None:
        return []

    if isinstance(payload, list):
        return payload

    if isinstance(payload, tuple):
        return list(payload)

    if isinstance(payload, dict):
        preferred_keys = (
            "evidence_items",
            "brief_items",
            "selected_items",
            "research_items",
            "items",
            "results",
            "sources",
            "documents",
            "links",
            "brief",
        )

        for key in preferred_keys:
            value = payload.get(key)
            if isinstance(value, (list, tuple)) and value:
                return list(value)

        # Some stores keep the useful payload nested.
        for key in ("data", "payload", "store", "research_brief", "newsroom_brief"):
            value = payload.get(key)
            nested = _extract_list_candidates(value)
            if nested:
                return nested

    return []


def _coerce_item(raw: Any, *, fallback_index: int) -> dict[str, Any] | None:
    if raw is None:
        return None

    if hasattr(raw, "to_dict") and callable(raw.to_dict):
        try:
            raw = raw.to_dict()
        except Exception:
            pass

    if hasattr(raw, "__dict__") and not isinstance(raw, dict):
        try:
            raw = vars(raw)
        except Exception:
            pass

    if isinstance(raw, str):
        text = _clean_text(raw)
        if not text:
            return None
        return {
            "id": f"text-{fallback_index}",
            "title": text[:90],
            "summary": text,
            "source": "Provided brief text",
            "url": "",
            "domain": "",
            "source_type": "source",
            "validity": "unknown",
            "relevance": "medium",
            "confidence": "medium",
            "published_at": "",
            "used_for_ai": True,
        }

    if not isinstance(raw, dict):
        return None

    item = dict(raw)

    title = _clean_text(
        _first_present(
            item,
            (
                "title",
                "headline",
                "name",
                "series_title",
                "label",
                "source_title",
            ),
            "",
        ),
        max_len=220,
    )

    summary = _clean_text(
        _first_present(
            item,
            (
                "summary",
                "description",
                "snippet",
                "abstract",
                "note",
                "notes",
                "reason",
                "text",
                "content",
            ),
            "",
        ),
        max_len=1600,
    )

    source = _clean_text(
        _first_present(
            item,
            (
                "source",
                "source_name",
                "publisher",
                "provider",
                "agency",
                "origin",
            ),
            "",
        ),
        max_len=180,
    )

    url = _clean_text(
        _first_present(
            item,
            (
                "url",
                "link",
                "href",
                "source_url",
                "reference_url",
                "api_url",
            ),
            "",
        ),
        max_len=800,
    )

    published_at = _clean_text(
        _first_present(
            item,
            (
                "published_at",
                "published",
                "date",
                "observation_date",
                "release_date",
                "updated_at",
                "last_updated",
            ),
            "",
        ),
        max_len=120,
    )

    if not title and summary:
        title = summary[:90]

    if not title and source:
        title = f"{source} item"

    if not title:
        return None

    domain = _domain_from_url(url)
    source_type = _source_type_from_item(item, domain)

    relevance = _clean_text(
        _first_present(item, ("relevance", "relevance_label", "importance"), "medium"),
        max_len=80,
    ) or "medium"

    confidence = _clean_text(
        _first_present(item, ("confidence", "confidence_label", "reliability"), "medium"),
        max_len=80,
    ) or "medium"

    validity = _clean_text(
        _first_present(item, ("validity", "validity_label", "trust_label"), ""),
        max_len=80,
    ) or _validity_label(source_type, domain, item)

    return {
        "id": str(_first_present(item, ("id", "uid", "key"), f"item-{fallback_index}")),
        "title": title,
        "summary": summary,
        "source": source or domain or "Unknown source",
        "url": url,
        "domain": domain,
        "source_type": source_type,
        "validity": validity,
        "relevance": relevance,
        "confidence": confidence,
        "published_at": published_at,
        "used_for_ai": bool(item.get("used_for_ai", True)),
        "raw_keys": sorted(str(k) for k in item.keys()),
    }


def extract_newsroom_evidence_items(
    newsroom_payload: Any,
    *,
    max_items: int = 16,
) -> list[dict[str, Any]]:
    """
    Convert current Newsroom result/brief store data into compact evidence items.

    The function accepts several store shapes because Newsroom has evolved over
    multiple patches. It is intentionally tolerant: dicts, dataclasses,
    dataframe-like records, raw strings, and nested payloads are all normalized.
    """

    candidates = _extract_list_candidates(newsroom_payload)
    out: list[dict[str, Any]] = []

    for index, raw in enumerate(candidates, start=1):
        item = _coerce_item(raw, fallback_index=index)
        if item is not None:
            out.append(item)

        if len(out) >= max_items:
            break

    return out


def build_newsroom_evidence_packet(
    newsroom_payload: Any,
    *,
    question: str = "",
    symbol: str = "",
    topic: str = "",
    max_items: int = 16,
) -> dict[str, Any]:
    """
    Build the AI Research Analyst evidence packet from Newsroom store data.

    This packet is intentionally a plain dict so it can be stored in Dash,
    exported as JSON, and sent to the LLM layer without custom serialization.
    """

    items = extract_newsroom_evidence_items(newsroom_payload, max_items=max_items)

    official_count = sum(1 for item in items if item.get("source_type") == "official")
    filing_count = sum(1 for item in items if item.get("source_type") == "filing")
    linked_count = sum(1 for item in items if item.get("url"))

    source_links = [
        {
            "title": item.get("title", ""),
            "source": item.get("source", ""),
            "url": item.get("url", ""),
            "domain": item.get("domain", ""),
            "validity": item.get("validity", "unknown"),
        }
        for item in items
        if item.get("url")
    ]

    packet = {
        "packet_type": "newsroom_research_evidence",
        "schema_version": "1.0",
        "generated_at": _now_iso(),
        "question": _clean_text(question, max_len=500),
        "symbol": _clean_text(symbol.upper() if symbol else "", max_len=32),
        "topic": _clean_text(topic, max_len=240),
        "item_count": len(items),
        "source_counts": {
            "official": official_count,
            "filing": filing_count,
            "linked": linked_count,
            "total": len(items),
        },
        "items": items,
        "source_links": source_links,
        "ai_grounding_rules": [
            "Use only the evidence items in this packet for current facts.",
            "If evidence is missing or stale, say so clearly.",
            "Separate confirmed facts from interpretation.",
            "Cite or mention source titles/links when making factual claims.",
            "Do not invent article contents that are not present in the packet.",
        ],
    }

    return packet


def evidence_packet_to_markdown(packet: dict[str, Any]) -> str:
    """Render a compact markdown context block for the AI prompt."""

    if not isinstance(packet, dict):
        return ""

    lines: list[str] = []
    lines.append("# Research Analyst Evidence Packet")
    if packet.get("question"):
        lines.append(f"Question: {packet.get('question')}")
    if packet.get("symbol"):
        lines.append(f"Symbol: {packet.get('symbol')}")
    if packet.get("topic"):
        lines.append(f"Topic: {packet.get('topic')}")
    lines.append(f"Generated: {packet.get('generated_at', '')}")
    lines.append(f"Items: {packet.get('item_count', 0)}")
    lines.append("")

    lines.append("## Grounding Rules")
    for rule in packet.get("ai_grounding_rules", []):
        lines.append(f"- {rule}")

    lines.append("")
    lines.append("## Evidence Items")

    for idx, item in enumerate(packet.get("items", []) or [], start=1):
        title = item.get("title", "Untitled")
        source = item.get("source", "Unknown source")
        validity = item.get("validity", "unknown")
        relevance = item.get("relevance", "medium")
        confidence = item.get("confidence", "medium")
        published_at = item.get("published_at", "")
        url = item.get("url", "")
        summary = item.get("summary", "")

        lines.append(f"### {idx}. {title}")
        lines.append(
            f"Source: {source} | Validity: {validity} | "
            f"Relevance: {relevance} | Confidence: {confidence}"
        )
        if published_at:
            lines.append(f"Published/Updated: {published_at}")
        if url:
            lines.append(f"Link: {url}")
        if summary:
            lines.append(f"Summary: {summary}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def build_research_analyst_context_from_newsroom(
    newsroom_payload: Any,
    *,
    question: str = "",
    symbol: str = "",
    topic: str = "",
    max_items: int = 16,
) -> str:
    packet = build_newsroom_evidence_packet(
        newsroom_payload,
        question=question,
        symbol=symbol,
        topic=topic,
        max_items=max_items,
    )
    return evidence_packet_to_markdown(packet)
