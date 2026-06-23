from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from html import unescape
from typing import Any
from urllib.request import Request, urlopen
import re
import xml.etree.ElementTree as ET

from .source_registry import ResearchSource, build_default_source_registry


@dataclass
class NewsItem:
    source_id: str
    source_name: str
    title: str
    link: str
    published: str = ""
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _clean_text(value: str | None, max_len: int = 800) -> str:
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", " ", str(value))
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        return text[: max_len - 3].rstrip() + "..."
    return text


def _child_text(element: ET.Element, names: list[str]) -> str:
    for name in names:
        child = element.find(name)
        if child is not None and child.text:
            return child.text

    wanted = {name.split("}")[-1].lower() for name in names}
    for child in list(element):
        tag = child.tag.split("}")[-1].lower()
        if tag in wanted and child.text:
            return child.text
    return ""


def fetch_news_feed(source: ResearchSource, per_feed: int = 5, timeout: float = 10.0) -> list[NewsItem]:
    if not source.rss_url:
        return []

    request = Request(
        source.rss_url,
        headers={
            "User-Agent": "AlgoTraderResearchBot/0.1 local-development",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.5",
        },
    )

    with urlopen(request, timeout=timeout) as response:
        raw = response.read()

    root = ET.fromstring(raw)
    items: list[NewsItem] = []

    for item in root.findall(".//item"):
        title = _clean_text(_child_text(item, ["title"]), 300)
        link = _clean_text(_child_text(item, ["link"]), 1000)
        published = _clean_text(_child_text(item, ["pubDate", "published", "updated"]), 200)
        summary = _clean_text(_child_text(item, ["description", "summary", "content"]), 800)
        if title:
            items.append(
                NewsItem(
                    source_id=source.id,
                    source_name=source.name,
                    title=title,
                    link=link,
                    published=published,
                    summary=summary,
                )
            )
        if len(items) >= per_feed:
            return items

    atom_entries = root.findall(".//{http://www.w3.org/2005/Atom}entry") + root.findall(".//entry")
    for entry in atom_entries:
        title = _clean_text(_child_text(entry, ["{http://www.w3.org/2005/Atom}title", "title"]), 300)
        link = ""
        for child in list(entry):
            tag = child.tag.split("}")[-1].lower()
            if tag == "link":
                link = child.attrib.get("href", "") or (child.text or "")
                break
        published = _clean_text(
            _child_text(entry, ["{http://www.w3.org/2005/Atom}published", "{http://www.w3.org/2005/Atom}updated", "published", "updated"]),
            200,
        )
        summary = _clean_text(_child_text(entry, ["{http://www.w3.org/2005/Atom}summary", "summary", "content"]), 800)
        if title:
            items.append(
                NewsItem(
                    source_id=source.id,
                    source_name=source.name,
                    title=title,
                    link=link,
                    published=published,
                    summary=summary,
                )
            )
        if len(items) >= per_feed:
            return items

    return items[:per_feed]


def fetch_news_feeds(per_feed: int = 3, timeout: float = 10.0) -> tuple[list[NewsItem], list[str]]:
    news: list[NewsItem] = []
    errors: list[str] = []

    for source in build_default_source_registry():
        if not source.rss_url:
            continue
        try:
            news.extend(fetch_news_feed(source, per_feed=per_feed, timeout=timeout))
        except Exception as exc:
            errors.append(f"{source.name}: {exc}")

    return news, errors


def news_items_markdown(items: list[NewsItem], errors: list[str] | None = None) -> str:
    lines = [
        "# Economic News Brief",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
    ]

    if not items:
        lines.append("No news items were fetched.")
    else:
        for item in items:
            lines.append(f"## {item.title}")
            lines.append(f"- Source: {item.source_name}")
            if item.published:
                lines.append(f"- Published: {item.published}")
            if item.link:
                lines.append(f"- Link: {item.link}")
            if item.summary:
                lines.append("")
                lines.append(item.summary)
            lines.append("")

    if errors:
        lines.append("## Feed errors")
        for error in errors:
            lines.append(f"- {error}")

    return "\n".join(lines)
