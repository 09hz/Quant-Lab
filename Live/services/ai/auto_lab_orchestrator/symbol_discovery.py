from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import re
from typing import Any


@dataclass(frozen=True)
class SymbolCandidate:
    symbol: str
    score: float
    reason: str
    source: str
    tags: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


PEER_MAP: dict[str, list[tuple[str, str]]] = {
    "AMD": [
        ("NVDA", "AI accelerator / GPU peer"),
        ("AVGO", "large-cap semiconductor peer"),
        ("QCOM", "semiconductor and edge compute peer"),
        ("MU", "memory cycle exposure"),
        ("INTC", "CPU / data-center chip peer"),
        ("TSM", "semiconductor foundry exposure"),
        ("ASML", "semiconductor equipment exposure"),
        ("MRVL", "data-center semiconductor peer"),
        ("SMH", "semiconductor ETF benchmark"),
        ("SOXX", "semiconductor ETF benchmark"),
    ],
    "NVDA": [
        ("AMD", "GPU / AI accelerator peer"),
        ("AVGO", "AI infrastructure semiconductor peer"),
        ("TSM", "semiconductor foundry exposure"),
        ("ASML", "semiconductor equipment exposure"),
        ("MU", "memory / AI infrastructure exposure"),
        ("MRVL", "data-center semiconductor peer"),
        ("ARM", "CPU architecture / AI edge exposure"),
        ("SMH", "semiconductor ETF benchmark"),
        ("SOXX", "semiconductor ETF benchmark"),
    ],
    "MSFT": [
        ("AAPL", "mega-cap technology peer"),
        ("GOOGL", "cloud / AI platform peer"),
        ("AMZN", "cloud platform peer"),
        ("META", "AI / digital advertising peer"),
        ("ORCL", "enterprise software / cloud peer"),
        ("CRM", "enterprise software peer"),
        ("IGV", "software ETF benchmark"),
        ("XLK", "technology sector ETF benchmark"),
    ],
    "AAPL": [
        ("MSFT", "mega-cap technology peer"),
        ("GOOGL", "mega-cap technology peer"),
        ("AMZN", "mega-cap technology peer"),
        ("META", "mega-cap technology peer"),
        ("QCOM", "device semiconductor supplier exposure"),
        ("TSM", "device supply-chain exposure"),
        ("XLK", "technology sector ETF benchmark"),
    ],
    "TSLA": [
        ("RIVN", "electric vehicle peer"),
        ("GM", "auto manufacturer benchmark"),
        ("F", "auto manufacturer benchmark"),
        ("NIO", "EV peer with higher risk"),
        ("LCID", "EV peer with higher risk"),
        ("XLY", "consumer discretionary benchmark"),
    ],
}

THEME_MAP: dict[str, list[tuple[str, str]]] = {
    "semiconductor": [
        ("AMD", "semiconductor theme seed"),
        ("NVDA", "AI semiconductor leader"),
        ("AVGO", "large-cap semiconductor / AI infrastructure"),
        ("QCOM", "mobile and edge semiconductor"),
        ("MU", "memory cycle"),
        ("TSM", "foundry exposure"),
        ("ASML", "equipment exposure"),
        ("MRVL", "data-center semiconductor"),
        ("SMH", "semiconductor ETF benchmark"),
        ("SOXX", "semiconductor ETF benchmark"),
    ],
    "chip": [
        ("AMD", "chip theme"),
        ("NVDA", "chip theme"),
        ("AVGO", "chip theme"),
        ("QCOM", "chip theme"),
        ("MU", "chip theme"),
        ("SMH", "chip ETF benchmark"),
    ],
    "ai": [
        ("NVDA", "AI infrastructure bellwether"),
        ("AMD", "AI accelerator exposure"),
        ("MSFT", "AI platform / cloud exposure"),
        ("GOOGL", "AI platform exposure"),
        ("META", "AI and ad-tech exposure"),
        ("AVGO", "AI networking / custom silicon exposure"),
        ("TSM", "AI chip foundry exposure"),
        ("ARM", "AI edge architecture exposure"),
        ("SMH", "AI semiconductor basket"),
        ("XLK", "technology benchmark"),
    ],
    "cloud": [
        ("MSFT", "cloud platform"),
        ("AMZN", "cloud platform"),
        ("GOOGL", "cloud platform"),
        ("ORCL", "enterprise cloud"),
        ("CRM", "enterprise software cloud"),
        ("SNOW", "cloud data platform"),
        ("IGV", "software ETF benchmark"),
    ],
    "software": [
        ("MSFT", "software mega-cap"),
        ("ORCL", "enterprise software"),
        ("CRM", "enterprise software"),
        ("ADBE", "creative software"),
        ("NOW", "workflow software"),
        ("PANW", "security software"),
        ("IGV", "software ETF benchmark"),
    ],
    "cyber": [
        ("PANW", "cybersecurity large cap"),
        ("CRWD", "endpoint security"),
        ("ZS", "zero-trust security"),
        ("FTNT", "network security"),
        ("OKTA", "identity security"),
        ("HACK", "cybersecurity ETF benchmark"),
    ],
    "energy": [
        ("XOM", "integrated energy"),
        ("CVX", "integrated energy"),
        ("COP", "energy producer"),
        ("SLB", "oilfield services"),
        ("XLE", "energy sector ETF benchmark"),
    ],
    "financial": [
        ("JPM", "banking benchmark"),
        ("BAC", "banking benchmark"),
        ("GS", "capital markets benchmark"),
        ("MS", "capital markets benchmark"),
        ("XLF", "financial sector ETF benchmark"),
    ],
    "health": [
        ("UNH", "managed care"),
        ("LLY", "pharma / obesity drug exposure"),
        ("JNJ", "healthcare large cap"),
        ("MRK", "pharma large cap"),
        ("XLV", "healthcare ETF benchmark"),
    ],
    "defense": [
        ("LMT", "defense prime"),
        ("RTX", "defense / aerospace"),
        ("NOC", "defense prime"),
        ("GD", "defense prime"),
        ("ITA", "aerospace and defense ETF benchmark"),
    ],
    "ev": [
        ("TSLA", "EV benchmark"),
        ("RIVN", "EV peer"),
        ("GM", "auto benchmark"),
        ("F", "auto benchmark"),
        ("XLY", "consumer discretionary benchmark"),
    ],
}


LIQUID_RESEARCH_HINTS = {
    "SPY", "QQQ", "DIA", "IWM", "XLK", "XLF", "XLE", "XLV", "XLY", "SMH", "SOXX", "IGV", "HACK", "ITA",
    "AAPL", "MSFT", "NVDA", "AMD", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "QCOM", "MU", "INTC", "TSM", "ASML",
    "MRVL", "ARM", "ORCL", "CRM", "ADBE", "NOW", "PANW", "CRWD", "JPM", "BAC", "GS", "MS", "XOM", "CVX", "UNH",
    "LLY", "JNJ", "MRK", "LMT", "RTX", "NOC", "GD", "RIVN", "GM", "F",
}


def normalize_symbols(value: str | list[str] | None) -> list[str]:
    if isinstance(value, list):
        raw_tokens = value
    else:
        raw_tokens = re.split(r"[,;\s]+", value or "")

    out: list[str] = []
    for raw in raw_tokens:
        symbol = str(raw).strip().upper()
        if not symbol:
            continue
        if not re.match(r"^[A-Z][A-Z0-9.\-]{0,9}$", symbol):
            continue
        out.append(symbol)
    return list(dict.fromkeys(out))


def _theme_tokens(theme: str | None) -> list[str]:
    text = (theme or "").lower()
    tokens = []
    for key in THEME_MAP:
        if key in text:
            tokens.append(key)
    if "artificial intelligence" in text and "ai" not in tokens:
        tokens.append("ai")
    if "semiconductors" in text and "semiconductor" not in tokens:
        tokens.append("semiconductor")
    return list(dict.fromkeys(tokens))


def _add_candidate(
    bucket: dict[str, SymbolCandidate],
    symbol: str,
    score: float,
    reason: str,
    source: str,
    tags: list[str],
) -> None:
    symbol = symbol.upper()
    liquidity_bonus = 0.10 if symbol in LIQUID_RESEARCH_HINTS else 0.0
    final_score = round(score + liquidity_bonus, 4)

    if symbol in bucket:
        old = bucket[symbol]
        merged_tags = list(dict.fromkeys([*old.tags, *tags]))
        merged_reason = old.reason
        if reason not in merged_reason:
            merged_reason = f"{old.reason}; {reason}"
        bucket[symbol] = SymbolCandidate(
            symbol=symbol,
            score=round(max(old.score, final_score) + 0.03, 4),
            reason=merged_reason,
            source=f"{old.source}+{source}",
            tags=merged_tags,
        )
    else:
        bucket[symbol] = SymbolCandidate(
            symbol=symbol,
            score=final_score,
            reason=reason,
            source=source,
            tags=list(dict.fromkeys(tags)),
        )


def discover_symbol_universe(
    seed_symbols: str | list[str] | None,
    theme: str | None = None,
    max_symbols: int = 10,
) -> dict[str, Any]:
    seeds = normalize_symbols(seed_symbols)
    max_symbols = max(1, min(int(max_symbols or 10), 30))

    candidates: dict[str, SymbolCandidate] = {}

    for seed in seeds:
        _add_candidate(
            candidates,
            seed,
            1.00,
            "Seed symbol supplied by user.",
            "seed",
            ["seed", "user_supplied"],
        )
        for peer, reason in PEER_MAP.get(seed, []):
            _add_candidate(
                candidates,
                peer,
                0.82,
                f"Peer/benchmark related to {seed}: {reason}.",
                f"peer:{seed}",
                ["peer", "related_universe"],
            )

    theme_hits = _theme_tokens(theme)
    for token in theme_hits:
        for symbol, reason in THEME_MAP.get(token, []):
            _add_candidate(
                candidates,
                symbol,
                0.72,
                f"Theme match `{token}`: {reason}.",
                f"theme:{token}",
                ["theme_match", token],
            )

    if not candidates:
        for symbol, reason in THEME_MAP["semiconductor"][:max_symbols]:
            _add_candidate(
                candidates,
                symbol,
                0.55,
                f"Default research universe fallback: {reason}.",
                "default",
                ["default", "research_universe"],
            )

    ranked = sorted(
        candidates.values(),
        key=lambda c: (-c.score, c.symbol),
    )[:max_symbols]

    suggested_symbols = [item.symbol for item in ranked]

    return {
        "schema_version": "auto_lab_symbol_discovery_v22_3",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "research_simulation_only",
        "seed_symbols": seeds,
        "theme": theme or "",
        "theme_hits": theme_hits,
        "max_symbols": max_symbols,
        "suggested_symbols": suggested_symbols,
        "ranked_candidates": [item.to_dict() for item in ranked],
        "safety_note": "Symbols are suggested for research/testing only. This is not a buy/sell recommendation.",
    }
