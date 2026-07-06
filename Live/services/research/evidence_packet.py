from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse
import re


OFFICIAL_DOMAINS = {
    "fred.stlouisfed.org", "api.stlouisfed.org", "bea.gov", "apps.bea.gov",
    "bls.gov", "api.bls.gov", "sec.gov", "www.sec.gov",
    "federalreserve.gov", "www.federalreserve.gov", "fiscaldata.treasury.gov",
}
MAJOR_NEWS_DOMAINS = {
    "reuters.com", "www.reuters.com", "apnews.com", "www.apnews.com",
    "bloomberg.com", "www.bloomberg.com", "cnbc.com", "www.cnbc.com",
    "marketwatch.com", "www.marketwatch.com", "finance.yahoo.com",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    try:
        value = str(value).strip()
    except Exception:
        return default
    return value or default


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _get(obj: Any, keys: Sequence[str], default: Any = None) -> Any:
    for key in keys:
        try:
            if isinstance(obj, Mapping) and key in obj and obj.get(key) not in (None, ""):
                return obj.get(key)
        except Exception:
            pass
        try:
            value = getattr(obj, key)
            if value not in (None, ""):
                return value
        except Exception:
            pass
    return default


def _domain(url: str) -> str:
    try:
        return (urlparse(_text(url)).netloc or "").lower().strip()
    except Exception:
        return ""


def _tokens(text: str) -> set[str]:
    stop = {"the", "and", "for", "with", "from", "that", "this", "latest", "market", "stock", "news"}
    return {w for w in re.findall(r"[A-Za-z0-9$_.-]{2,}", _text(text).lower()) if w not in stop}


def classify_source_type(publisher: str = "", url: str = "", explicit: str = "") -> str:
    explicit = _text(explicit).lower()
    if explicit in {"official", "filing", "major_news", "research", "blog", "social", "unknown"}:
        return explicit
    if explicit == "news":
        return "major_news"

    host = _domain(url)
    publisher_l = publisher.lower()
    if host in OFFICIAL_DOMAINS or any(x in publisher_l for x in ("fred", "bea", "bls", "federal reserve", "treasury")):
        return "official"
    if "sec" in publisher_l or "sec.gov" in host:
        return "filing"
    if host in MAJOR_NEWS_DOMAINS or any(x in publisher_l for x in ("reuters", "bloomberg", "cnbc", "ap news")):
        return "major_news"
    if any(x in publisher_l for x in ("blog", "substack", "medium")):
        return "blog"
    return "unknown"


@dataclass
class EvidenceSource:
    title: str = ""
    publisher: str = ""
    url: str = ""
    published_at: str = ""
    source_type: str = "unknown"
    primary: bool = False
    domain: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvidenceItem:
    title: str
    summary: str
    source: EvidenceSource
    values: dict[str, Any] = field(default_factory=dict)
    relevance: float = 0.0
    confidence: float = 0.0
    validity: str = "unknown"
    highlights: list[str] = field(default_factory=list)
    tickers: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source"] = self.source.as_dict()
        return data

    def compact_line(self, index: int) -> str:
        publisher = self.source.publisher or self.source.domain or "Unknown source"
        primary = "primary" if self.source.primary else "secondary"
        url = f" [{self.source.url}]" if self.source.url else ""
        return (
            f"{index}. {self.title} - {publisher}; type={self.source.source_type}; "
            f"{primary}; relevance={self.relevance:.2f}; confidence={self.confidence:.2f}.{url}"
        )


@dataclass
class EvidencePacket:
    question: str
    topic: str
    symbol: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    items: list[EvidenceItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    instructions: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "topic": self.topic,
            "symbol": self.symbol,
            "created_at": self.created_at,
            "items": [item.as_dict() for item in self.items],
            "warnings": list(self.warnings),
            "instructions": list(self.instructions),
        }

    def source_links(self) -> list[dict[str, str]]:
        links = []
        seen = set()
        for item in self.items:
            url = item.source.url
            if not url or url in seen:
                continue
            seen.add(url)
            links.append({
                "title": item.title,
                "publisher": item.source.publisher,
                "url": url,
                "source_type": item.source.source_type,
                "published_at": item.source.published_at,
            })
        return links

    def to_markdown(self, max_summary_chars: int = 800) -> str:
        lines = [
            "# Research Analyst Evidence Packet",
            "",
            f"Question: {self.question or 'Not provided'}",
        ]
        if self.symbol:
            lines.append(f"Symbol: {self.symbol}")
        lines += [
            f"Topic: {self.topic or 'general'}",
            f"Created: {self.created_at}",
            "",
            "## Answering Rules",
        ]
        for rule in self.instructions or [
            "Use only the evidence items below for current facts.",
            "Do not claim live research unless an evidence item supports it.",
            "Separate confirmed facts from inference.",
            "Include source links when possible.",
        ]:
            lines.append(f"- {rule}")

        if self.warnings:
            lines += ["", "## Validity Warnings"]
            for warning in self.warnings:
                lines.append(f"- {warning}")

        lines += ["", "## Evidence Items"]
        if not self.items:
            lines.append("- No evidence items were provided.")
        for idx, item in enumerate(self.items, start=1):
            lines.append(item.compact_line(idx))
            summary = item.summary.strip()
            if summary:
                if len(summary) > max_summary_chars:
                    summary = summary[: max_summary_chars - 3].rstrip() + "..."
                lines.append(f"   Summary: {summary}")
            for highlight in item.highlights[:5]:
                lines.append(f"   Highlight: {highlight}")
            if item.values:
                values = ", ".join(f"{k}={v}" for k, v in list(item.values.items())[:8])
                lines.append(f"   Values: {values}")

        lines += ["", "## Source Links"]
        links = self.source_links()
        if not links:
            lines.append("- No direct source links were included.")
        for idx, link in enumerate(links, start=1):
            date = f"; date={link['published_at']}" if link.get("published_at") else ""
            lines.append(
                f"{idx}. {link.get('publisher') or 'source'} - {link.get('title') or 'Untitled'}; "
                f"type={link.get('source_type') or 'unknown'}{date}; url={link.get('url') or ''}"
            )
        return "\n".join(lines).strip() + "\n"


def _primary(source_type: str, publisher: str, url: str, explicit: Any = None) -> bool:
    if isinstance(explicit, bool):
        return explicit
    host = _domain(url)
    text = publisher.lower()
    return source_type in {"official", "filing"} or host in OFFICIAL_DOMAINS or any(
        x in text for x in ("fred", "bea", "bls", "federal reserve", "sec", "treasury")
    )


def _score_relevance(item: EvidenceItem, question: str, symbol: str) -> float:
    q = _tokens(question)
    blob = " ".join([item.title, item.summary, item.source.publisher, " ".join(item.topics), " ".join(item.tickers)])
    i = _tokens(blob)
    overlap = min(0.7, len(q & i) / max(1, len(q))) if q else 0.35
    symbol_score = 0.25 if symbol and symbol.upper() in blob.upper() else 0.0
    source_score = 0.10 if item.source.primary else 0.06 if item.source.source_type == "major_news" else 0.0
    value_score = 0.05 if item.values else 0.0
    return round(max(0.0, min(1.0, overlap + symbol_score + source_score + value_score)), 3)


def _score_confidence(item: EvidenceItem) -> float:
    score = 0.25
    if item.source.primary:
        score += 0.35
    if item.source.source_type in {"official", "filing"}:
        score += 0.28
    elif item.source.source_type == "major_news":
        score += 0.22
    elif item.source.source_type == "blog":
        score += 0.05
    if item.source.url:
        score += 0.12
    if item.summary:
        score += 0.08
    if item.values:
        score += 0.07
    return round(max(0.0, min(1.0, score)), 3)


def normalize_research_item(raw: Any, question: str = "", symbol: str = "") -> EvidenceItem:
    source_obj = _get(raw, ("source", "source_info", "provider"), None)
    title = _text(_get(raw, ("title", "headline", "name", "series_title", "label"), "Untitled evidence item"))
    summary = _text(_get(raw, ("summary", "snippet", "description", "text", "body", "abstract", "note"), ""))
    url = _text(_get(raw, ("url", "link", "href", "source_url", "article_url"), ""))
    if not url:
        url = _text(_get(source_obj, ("url", "link", "href"), ""))

    publisher = _text(_get(raw, ("publisher", "source_name", "provider_name", "agency"), ""))
    if not publisher:
        publisher = _text(_get(source_obj, ("name", "source_name", "publisher", "label", "title"), ""))

    published_at = _text(_get(raw, ("published_at", "published", "publication_date", "date", "updated_at", "observation_date", "filing_date"), ""))
    source_type = classify_source_type(publisher, url, _text(_get(raw, ("source_type", "type", "category"), "")))
    primary = _primary(source_type, publisher, url, _get(raw, ("primary", "is_primary"), None))

    values = _get(raw, ("values", "metrics", "data", "latest_values"), {}) or {}
    if not isinstance(values, Mapping):
        values = {"value": values}
    values = dict(values)
    series_id = _get(raw, ("series_id", "fred_series_id", "bls_series_id"), "")
    value = _get(raw, ("value", "latest_value", "observation_value"), None)
    if series_id and value is not None:
        values.setdefault(str(series_id), value)

    highlights_raw = _get(raw, ("highlights", "key_points", "bullets"), []) or []
    if isinstance(highlights_raw, str):
        highlights = [highlights_raw]
    else:
        try:
            highlights = [_text(x) for x in highlights_raw if _text(x)]
        except Exception:
            highlights = []

    tickers_raw = _get(raw, ("tickers", "symbols"), []) or []
    if isinstance(tickers_raw, str):
        tickers = [tickers_raw.upper()]
    else:
        try:
            tickers = [_text(x).upper() for x in tickers_raw if _text(x)]
        except Exception:
            tickers = []
    if symbol and symbol.upper() not in tickers and symbol.upper() in f"{title} {summary}".upper():
        tickers.append(symbol.upper())

    topics_raw = _get(raw, ("topics", "tags"), []) or []
    if isinstance(topics_raw, str):
        topics = [topics_raw]
    else:
        try:
            topics = [_text(x) for x in topics_raw if _text(x)]
        except Exception:
            topics = []

    source = EvidenceSource(
        title=publisher,
        publisher=publisher,
        url=url,
        published_at=published_at,
        source_type=source_type,
        primary=primary,
        domain=_domain(url),
    )
    item = EvidenceItem(
        title=title,
        summary=summary,
        source=source,
        values=values,
        relevance=_num(_get(raw, ("relevance", "relevance_score"), 0.0)),
        confidence=_num(_get(raw, ("confidence", "confidence_score", "reliability"), 0.0)),
        highlights=highlights,
        tickers=tickers,
        topics=topics,
        raw=dict(raw) if isinstance(raw, Mapping) else {},
    )
    item.relevance = max(item.relevance, _score_relevance(item, question, symbol))
    item.confidence = max(item.confidence, _score_confidence(item))
    if item.source.primary and item.source.url:
        item.validity = "high"
    elif item.source.source_type == "major_news" and item.source.url:
        item.validity = "medium-high"
    elif item.source.url:
        item.validity = "medium"
    else:
        item.validity = "low"
    return item


class EvidencePacketBuilder:
    def build(
        self,
        question: str,
        raw_items: Sequence[Any],
        symbol: str = "",
        topic: str = "",
        max_items: int = 12,
    ) -> EvidencePacket:
        question = _text(question, "Summarize the provided market evidence.")
        symbol = _text(symbol).upper()
        topic = _text(topic, "market research")

        items = []
        for raw in raw_items or []:
            try:
                items.append(normalize_research_item(raw, question, symbol))
            except Exception as exc:
                items.append(EvidenceItem(
                    title="Evidence item could not be normalized",
                    summary=f"Normalization error: {exc}",
                    source=EvidenceSource(source_type="unknown"),
                    validity="low",
                ))

        items.sort(key=lambda x: (x.relevance, x.confidence, 1 if x.source.primary else 0, 1 if x.source.url else 0), reverse=True)
        kept = items[: max(1, int(max_items or 12))]

        warnings = []
        if not kept:
            warnings.append("No evidence items were provided.")
        if len(items) > len(kept):
            warnings.append(f"Evidence packet was truncated from {len(items)} items to {len(kept)} top-ranked items.")
        if kept and not any(x.source.url for x in kept):
            warnings.append("No evidence item includes a direct source link.")
        if kept and not any(x.source.primary for x in kept):
            warnings.append("No primary or official source was included.")
        if kept and len({x.source.publisher or x.source.domain or 'unknown' for x in kept}) == 1:
            warnings.append("All evidence came from a single publisher/source; cross-checking is limited.")

        instructions = [
            "Use only the evidence items in this packet for current facts.",
            "Do not invent dates, prices, events, or source claims.",
            "Separate confirmed facts from interpretation and trading implications.",
            "Call out low-confidence or single-source claims.",
            "Include the most relevant source links in the final answer.",
        ]

        return EvidencePacket(question=question, topic=topic, symbol=symbol, items=kept, warnings=warnings, instructions=instructions)


def build_evidence_packet(
    question: str,
    raw_items: Sequence[Any],
    symbol: str = "",
    topic: str = "",
    max_items: int = 12,
) -> EvidencePacket:
    return EvidencePacketBuilder().build(question, raw_items, symbol=symbol, topic=topic, max_items=max_items)
