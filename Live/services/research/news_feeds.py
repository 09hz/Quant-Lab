from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from email.utils import parsedate_to_datetime
from html import unescape
import re
from typing import Any
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET


@dataclass
class NewsItem:
    title: str
    source: str
    url: str = ""
    published: str = ""
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DEFAULT_FEEDS: list[dict[str, str]] = [
    {
        "key": "federal_reserve_press",
        "source": "Federal Reserve Press Releases",
        "url": "https://www.federalreserve.gov/feeds/press_all.xml",
    },
    {
        "key": "sec_press",
        "source": "SEC Press Releases",
        "url": "https://www.sec.gov/news/pressreleases.rss",
    },
    {
        "key": "bls_latest",
        "source": "BLS Latest Numbers",
        "url": "https://www.bls.gov/feed/bls_latest.rss",
    },
]


def strip_html(text: str) -> str:
    text = unescape(str(text or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _node_text(node: ET.Element | None, default: str = "") -> str:
    if node is None or node.text is None:
        return default
    return strip_html(node.text)


def _parse_date(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        return ""
    try:
        return parsedate_to_datetime(value).isoformat()
    except Exception:
        return value


def fetch_rss_feed(url: str, source: str = "", per_feed: int = 5, timeout: float = 12) -> list[NewsItem]:
    request = Request(
        url,
        headers={
            "User-Agent": "AlgoTraderResearchBot/0.1 research-only contact=local",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
        },
        method="GET",
    )

    with urlopen(request, timeout=timeout) as response:
        raw = response.read()

    root = ET.fromstring(raw)
    items: list[NewsItem] = []

    for item in root.findall(".//item"):
        if len(items) >= per_feed:
            break
        title = _node_text(item.find("title"))
        link = _node_text(item.find("link"))
        published = _parse_date(_node_text(item.find("pubDate")) or _node_text(item.find("date")))
        summary = _node_text(item.find("description"))
        if title:
            items.append(NewsItem(title=title, source=source or "RSS", url=link, published=published, summary=summary))

    if not items:
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall(".//atom:entry", ns):
            if len(items) >= per_feed:
                break
            title = _node_text(entry.find("atom:title", ns))
            link_node = entry.find("atom:link", ns)
            link = link_node.attrib.get("href", "") if link_node is not None else ""
            published = _parse_date(_node_text(entry.find("atom:updated", ns)) or _node_text(entry.find("atom:published", ns)))
            summary = _node_text(entry.find("atom:summary", ns))
            if title:
                items.append(NewsItem(title=title, source=source or "Atom", url=link, published=published, summary=summary))

    return items


def fetch_default_news(per_feed: int = 3, timeout: float = 12) -> list[NewsItem]:
    results: list[NewsItem] = []
    for feed in DEFAULT_FEEDS:
        try:
            results.extend(fetch_rss_feed(feed["url"], source=feed["source"], per_feed=per_feed, timeout=timeout))
        except Exception as exc:
            results.append(
                NewsItem(
                    title=f"Feed unavailable: {feed['source']}",
                    source=feed["source"],
                    summary=str(exc),
                    published=datetime.now().isoformat(timespec="seconds"),
                )
            )
    return results
