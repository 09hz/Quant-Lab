from __future__ import annotations

from typing import Iterable


NOISE_SYMBOLS = {
    "AI", "API", "APP", "ASK", "BID", "BUY", "CASH", "CEO", "CFO", "CSV", "DB",
    "DEBUG", "ENV", "ERROR", "FAIL", "FALSE", "GDP", "HOLD", "IB", "JSON",
    "LIVE", "LOG", "MACD", "MD", "NEWS", "NO", "PASS", "PDF", "POLL", "QA",
    "RSI", "RUN", "SEC", "SELL", "SEND", "SQL", "TRUE", "UI", "USD", "WARN", "YES",
}


VALID_RESEARCH_SYMBOLS = {
    "SPY", "QQQ", "DIA", "IWM", "VTI", "VOO",
    "XLK", "XLF", "XLE", "XLV", "XLY", "XLI", "XLP", "XLU", "XLB", "XLRE", "XLC",
    "SMH", "SOXX", "IGV", "HACK", "ITA", "ARKK",
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "GOOG", "META", "TSLA", "ORCL", "CRM", "ADBE", "NOW", "SNOW",
    "AMD", "AVGO", "QCOM", "MU", "INTC", "TSM", "ASML", "MRVL", "ARM", "LRCX", "KLAC", "AMAT", "NXPI", "MCHP", "ADI", "TXN", "ON",
    "PANW", "CRWD", "ZS", "FTNT", "OKTA",
    "JPM", "BAC", "GS", "MS", "WFC", "C", "BLK",
    "XOM", "CVX", "COP", "SLB", "EOG", "OXY",
    "UNH", "LLY", "JNJ", "MRK", "PFE", "ABBV", "TMO",
    "LMT", "RTX", "NOC", "GD", "BA", "CAT", "DE",
    "RIVN", "GM", "F", "NIO", "LCID", "DIS", "WMT", "COST", "HD",
}


THEME_SYMBOL_MAP = {
    "semiconductor": {
        "AMD", "NVDA", "AVGO", "QCOM", "MU", "INTC", "TSM", "ASML", "MRVL", "ARM",
        "LRCX", "KLAC", "AMAT", "NXPI", "MCHP", "ADI", "TXN", "ON", "SMH", "SOXX",
    },
    "semiconductors": {
        "AMD", "NVDA", "AVGO", "QCOM", "MU", "INTC", "TSM", "ASML", "MRVL", "ARM",
        "LRCX", "KLAC", "AMAT", "NXPI", "MCHP", "ADI", "TXN", "ON", "SMH", "SOXX",
    },
    "ai infrastructure": {
        "AMD", "NVDA", "AVGO", "TSM", "ASML", "MRVL", "ARM", "MSFT", "GOOGL", "AMZN", "META", "SMH", "SOXX", "XLK",
    },
    "cloud": {"MSFT", "AMZN", "GOOGL", "ORCL", "CRM", "SNOW", "IGV", "XLK"},
    "cyber": {"PANW", "CRWD", "ZS", "FTNT", "OKTA", "HACK"},
    "energy": {"XOM", "CVX", "COP", "SLB", "EOG", "OXY", "XLE"},
    "financial": {"JPM", "BAC", "GS", "MS", "WFC", "C", "BLK", "XLF"},
    "health": {"UNH", "LLY", "JNJ", "MRK", "PFE", "ABBV", "TMO", "XLV"},
    "defense": {"LMT", "RTX", "NOC", "GD", "BA", "ITA"},
    "ev": {"TSLA", "RIVN", "GM", "F", "NIO", "LCID", "XLY"},
}


def is_valid_research_symbol(symbol: str, known_symbols: Iterable[str] | None = None) -> bool:
    value = str(symbol or "").strip().upper()
    if not value:
        return False
    if value in NOISE_SYMBOLS:
        return False
    if len(value) > 10:
        return False
    if not value.replace(".", "").replace("-", "").isalnum():
        return False

    known = {str(item).strip().upper() for item in (known_symbols or [])}
    return value in VALID_RESEARCH_SYMBOLS or value in known


def clean_symbol_list(symbols: Iterable[str] | None, known_symbols: Iterable[str] | None = None) -> list[str]:
    out: list[str] = []
    for raw in symbols or []:
        symbol = str(raw or "").strip().upper()
        if is_valid_research_symbol(symbol, known_symbols=known_symbols):
            out.append(symbol)
    return list(dict.fromkeys(out))


def requested_theme_symbol_multiplier(symbol: str, requested_theme: str = "") -> float:
    """Return a ranking multiplier for a requested research theme.

    This only changes research-packet ranking. It does not create trade signals.
    """
    symbol = str(symbol or "").upper().strip()
    text = str(requested_theme or "").lower()

    if not text:
        return 1.0

    matched_any_theme = False
    matched_symbol_theme = False

    for token, theme_symbols in THEME_SYMBOL_MAP.items():
        if token in text:
            matched_any_theme = True
            if symbol in theme_symbols:
                matched_symbol_theme = True

    if matched_symbol_theme:
        return 2.75
    if matched_any_theme:
        return 0.35
    return 1.0
