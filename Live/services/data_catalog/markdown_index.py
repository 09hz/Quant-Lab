from __future__ import annotations

from pathlib import Path
import re


HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*$")


def parse_markdown(path: Path, max_preview: int = 4000) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    headings = []
    for line in lines:
        m = HEADING_RE.match(line)
        if m:
            headings.append(m.group(2).strip())
    words = re.findall(r"\b[\w\-]+\b", text)
    return {
        "title": headings[0] if headings else path.stem.replace("_", " "),
        "headings": headings[:80],
        "preview_text": text.strip()[:max_preview],
        "word_count": len(words),
        "line_count": len(lines),
    }
