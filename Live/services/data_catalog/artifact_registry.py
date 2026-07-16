from __future__ import annotations

from pathlib import Path
import re


SYMBOL_RE = re.compile(r"\b[A-Z]{1,5}(?:\.[A-Z])?\b")


def _lower(path: Path) -> str:
    return "/".join(part.lower() for part in path.parts)


def classify_artifact(path: Path) -> str:
    low = _lower(path)
    ext = path.suffix.lower().lstrip(".")
    name = path.name.lower()
    if "data/catalog" in low or name.startswith("data_catalog.sqlite"):
        return "catalog_internal"
    if "market_memory" in low and "research_packet" in name:
        return "market_memory_packet"
    if "market_memory" in low and (ext == "md" or "report" in low):
        return "market_memory_report"
    if "walk" in low and "forward" in low:
        return "walk_forward_result"
    if "universe" in low and ("run" in low or "result" in low):
        return "universe_run"
    if "backtest" in low:
        return "backtest_result"
    if "strategy" in low:
        return "strategy_result"
    if "diagnostic" in low or "diag" in low:
        return "diagnostic_report"
    if "newsroom" in low or "news" in low:
        return "newsroom_export"
    if ext == "md":
        return "markdown_report"
    if ext == "json":
        return "json_export"
    if ext == "csv":
        return "csv_export"
    if ext in {"sqlite", "sqlite3", "db"}:
        return "sqlite_database"
    return "data_file"


def source_module(path: Path) -> str:
    low = _lower(path)
    if "market_memory" in low:
        return "market_memory"
    if "auto_lab" in low or "autolab" in low:
        return "ai_auto_lab"
    if "newsroom" in low:
        return "newsroom"
    if "backtest" in low:
        return "backtest"
    return ""


def infer_symbol(path: Path) -> str:
    noise = {"JSON", "CSV", "MD", "DATA", "RUN", "PASS", "WARN", "ERROR", "INFO"}
    for token in SYMBOL_RE.findall(path.stem.replace("_", " ")):
        token = token.upper()
        if token not in noise:
            return token
    return ""


def infer_theme(path: Path) -> str:
    text = path.stem.lower().replace("_", " ").replace("-", " ")
    if "ai infrastructure" in text and "semiconductor" in text:
        return "AI infrastructure semiconductors"
    if "semiconductor" in text:
        return "Semiconductors"
    if "consumer discretionary" in text:
        return "Consumer discretionary"
    if "cyber" in text:
        return "Cybersecurity"
    return ""


def tags_for(path: Path, artifact_type: str) -> list[str]:
    low = _lower(path)
    tags = {artifact_type}
    for token in ["market_memory", "research_packet", "backtest", "walk_forward", "universe", "newsroom", "diagnostic", "report"]:
        if token in low:
            tags.add(token)
    if path.suffix:
        tags.add(path.suffix.lower().lstrip("."))
    return sorted(tags)
