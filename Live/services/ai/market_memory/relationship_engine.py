from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .models import EntityRecord, RelationshipRecord, stable_hash, utc_now_iso


SYMBOL_NAME_MAP: dict[str, str] = {
    "AMD": "Advanced Micro Devices",
    "NVDA": "NVIDIA",
    "AVGO": "Broadcom",
    "QCOM": "Qualcomm",
    "MU": "Micron Technology",
    "INTC": "Intel",
    "TSM": "Taiwan Semiconductor Manufacturing",
    "ASML": "ASML",
    "MRVL": "Marvell Technology",
    "SMH": "VanEck Semiconductor ETF",
    "SOXX": "iShares Semiconductor ETF",
    "MSFT": "Microsoft",
    "AAPL": "Apple",
    "GOOGL": "Alphabet",
    "AMZN": "Amazon",
    "META": "Meta Platforms",
    "TSLA": "Tesla",
    "SPY": "S&P 500 ETF",
    "QQQ": "Nasdaq 100 ETF",
    "XLK": "Technology Sector ETF",
    "XLF": "Financial Sector ETF",
    "XLE": "Energy Sector ETF",
    "XLV": "Healthcare Sector ETF",
    "XLY": "Consumer Discretionary Sector ETF",
}

PEER_MAP: dict[str, list[str]] = {
    "AMD": ["NVDA", "AVGO", "QCOM", "MU", "INTC", "TSM", "ASML", "MRVL", "SMH", "SOXX"],
    "NVDA": ["AMD", "AVGO", "TSM", "ASML", "MU", "MRVL", "SMH", "SOXX"],
    "MSFT": ["AAPL", "GOOGL", "AMZN", "META", "XLK"],
    "AAPL": ["MSFT", "GOOGL", "AMZN", "META", "QCOM", "TSM", "XLK"],
    "TSLA": ["RIVN", "GM", "F", "XLY"],
}

THEME_KEYWORDS: dict[str, list[str]] = {
    "AI infrastructure": ["ai infrastructure", "artificial intelligence", "gpu", "accelerator", "data center", "datacenter"],
    "Semiconductors": ["semiconductor", "semiconductors", "chip", "chips", "foundry", "lithography"],
    "Cloud platforms": ["cloud", "azure", "aws", "gcp"],
    "Cybersecurity": ["cyber", "security", "ransomware", "zero trust"],
    "Interest rates": ["fed", "federal reserve", "rates", "inflation", "cpi", "treasury yield"],
    "Energy": ["oil", "gas", "energy", "opec", "crude"],
    "Defense": ["defense", "geopolitical", "missile", "aerospace"],
    "Consumer discretionary": ["consumer", "retail", "ev", "electric vehicle", "autos"],
    "Healthcare": ["healthcare", "pharma", "drug", "biotech", "medicare"],
}

SECTOR_HINTS: dict[str, str] = {
    "AMD": "Semiconductors",
    "NVDA": "Semiconductors",
    "AVGO": "Semiconductors",
    "QCOM": "Semiconductors",
    "MU": "Semiconductors",
    "INTC": "Semiconductors",
    "TSM": "Semiconductors",
    "ASML": "Semiconductors",
    "MRVL": "Semiconductors",
    "SMH": "Semiconductors",
    "SOXX": "Semiconductors",
    "MSFT": "Cloud platforms",
    "GOOGL": "Cloud platforms",
    "AMZN": "Cloud platforms",
    "META": "AI infrastructure",
    "TSLA": "Consumer discretionary",
}

SYMBOL_RE = re.compile(r"\b[A-Z]{1,5}(?:[.\-][A-Z]{1,3})?\b")


def normalize_symbol(value: str) -> str:
    return value.strip().upper()


def extract_symbols(text: str) -> list[str]:
    symbols: list[str] = []
    for match in SYMBOL_RE.findall(text or ""):
        symbol = normalize_symbol(match)
        if symbol in SYMBOL_NAME_MAP or symbol in PEER_MAP or len(symbol) >= 2:
            symbols.append(symbol)
    return list(dict.fromkeys(symbols))


def extract_themes(text: str) -> list[str]:
    lowered = (text or "").lower()
    themes: list[str] = []
    for theme, keywords in THEME_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            themes.append(theme)
    return list(dict.fromkeys(themes))


def extract_memory_signals(text: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    metadata = metadata or {}
    symbols = extract_symbols(text)
    explicit_symbols = metadata.get("symbols") or metadata.get("suggested_symbols") or []
    if isinstance(explicit_symbols, str):
        explicit_symbols = re.split(r"[,;\s]+", explicit_symbols)
    for raw in explicit_symbols:
        symbol = normalize_symbol(str(raw))
        if symbol:
            symbols.append(symbol)

    themes = extract_themes(text)
    explicit_themes = metadata.get("themes") or []
    if isinstance(explicit_themes, str):
        explicit_themes = [explicit_themes]
    for theme in explicit_themes:
        if str(theme).strip():
            themes.append(str(theme).strip())

    symbols = list(dict.fromkeys(symbols))
    themes = list(dict.fromkeys(themes))

    entities: list[dict[str, Any]] = []
    for symbol in symbols:
        entities.append(
            {
                "canonical_name": SYMBOL_NAME_MAP.get(symbol, symbol),
                "entity_type": "symbol",
                "symbol": symbol,
                "aliases": [symbol, SYMBOL_NAME_MAP.get(symbol, symbol)],
                "confidence": 0.70 if symbol in SYMBOL_NAME_MAP else 0.45,
            }
        )

    for theme in themes:
        entities.append(
            {
                "canonical_name": theme,
                "entity_type": "theme",
                "symbol": "",
                "aliases": [theme],
                "confidence": 0.60,
            }
        )

    return {
        "symbols": symbols,
        "themes": themes,
        "entities": entities,
    }


def entities_from_signals(signals: dict[str, Any], evidence_id: str) -> list[EntityRecord]:
    now = utc_now_iso()
    entities: list[EntityRecord] = []
    for item in signals.get("entities", []):
        entities.append(
            EntityRecord(
                canonical_name=item.get("canonical_name", ""),
                entity_type=item.get("entity_type", "unknown"),
                symbol=item.get("symbol", ""),
                aliases=item.get("aliases", []),
                first_seen_at=now,
                last_seen_at=now,
                source_count=1,
                confidence=float(item.get("confidence", 0.50)),
                metadata={"evidence_id": evidence_id},
            )
        )
    return [item for item in entities if item.canonical_name]


def relationship_id(source_entity: str, relationship_type: str, target_entity: str) -> str:
    return stable_hash(f"{source_entity}|{relationship_type}|{target_entity}", prefix="rel_")


def relationship_records_from_signals(
    signals: dict[str, Any],
    evidence_id: str,
    source_type: str,
) -> list[RelationshipRecord]:
    now = utc_now_iso()
    relationships: list[RelationshipRecord] = []
    symbols = list(dict.fromkeys(signals.get("symbols", [])))
    themes = list(dict.fromkeys(signals.get("themes", [])))

    for symbol in symbols:
        source_name = SYMBOL_NAME_MAP.get(symbol, symbol)

        sector = SECTOR_HINTS.get(symbol)
        if sector:
            relationships.append(
                RelationshipRecord(
                    id=relationship_id(source_name, "belongs_to_theme", sector),
                    source_entity=source_name,
                    target_entity=sector,
                    relationship_type="belongs_to_theme",
                    confidence=0.72,
                    impact_score=0.55,
                    recency_score=1.0,
                    evidence_count=1,
                    first_seen_at=now,
                    last_seen_at=now,
                    evidence_ids=[evidence_id],
                    metadata={"symbol": symbol, "source_type": source_type},
                )
            )

        for theme in themes:
            relationships.append(
                RelationshipRecord(
                    id=relationship_id(source_name, "exposed_to_theme", theme),
                    source_entity=source_name,
                    target_entity=theme,
                    relationship_type="exposed_to_theme",
                    confidence=0.62,
                    impact_score=0.50,
                    recency_score=1.0,
                    evidence_count=1,
                    first_seen_at=now,
                    last_seen_at=now,
                    evidence_ids=[evidence_id],
                    metadata={"symbol": symbol, "source_type": source_type},
                )
            )

        for peer in PEER_MAP.get(symbol, []):
            peer_name = SYMBOL_NAME_MAP.get(peer, peer)
            relationships.append(
                RelationshipRecord(
                    id=relationship_id(source_name, "related_to_symbol", peer_name),
                    source_entity=source_name,
                    target_entity=peer_name,
                    relationship_type="related_to_symbol",
                    confidence=0.68,
                    impact_score=0.45,
                    recency_score=1.0,
                    evidence_count=1,
                    first_seen_at=now,
                    last_seen_at=now,
                    evidence_ids=[evidence_id],
                    metadata={"symbol": symbol, "peer_symbol": peer, "source_type": source_type},
                )
            )

    for idx, theme_a in enumerate(themes):
        for theme_b in themes[idx + 1:]:
            relationships.append(
                RelationshipRecord(
                    id=relationship_id(theme_a, "co_occurs_with_theme", theme_b),
                    source_entity=theme_a,
                    target_entity=theme_b,
                    relationship_type="co_occurs_with_theme",
                    confidence=0.50,
                    impact_score=0.35,
                    recency_score=1.0,
                    evidence_count=1,
                    first_seen_at=now,
                    last_seen_at=now,
                    evidence_ids=[evidence_id],
                    metadata={"source_type": source_type},
                )
            )

    return relationships
