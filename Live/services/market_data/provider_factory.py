from __future__ import annotations

import os
from typing import Any

from services.market_data.base import MarketDataProvider
from services.market_data.csv_provider import CSVMarketDataProvider
from services.market_data.ibkr_provider import IBKRMarketDataProvider

try:
    from services.market_data.tradier_provider import TradierMarketDataProvider
except Exception:
    TradierMarketDataProvider = None


def get_market_data_provider_name(default: str = "ibkr") -> str:
    """
    Return the configured market data provider name.

    Supported values:
        ibkr
        csv
        tradier
    """
    return str(os.getenv("MARKET_DATA_PROVIDER", default) or default).strip().lower()


def should_start_ibkr(provider_name: str | None = None) -> bool:
    """
    Return True when the app should start the IBKR realtime adapter.

    CSV and Tradier modes should not autostart IBKR.
    """
    provider = str(provider_name or get_market_data_provider_name()).strip().lower()
    return provider in {"ibkr", "ib", "interactive_brokers", "interactive-brokers"}


def should_autostart_ibkr(provider_name: str | None = None) -> bool:
    """Compatibility alias."""
    return should_start_ibkr(provider_name)


def should_start_ibkr_connection(provider_name: str | None = None) -> bool:
    """Compatibility alias."""
    return should_start_ibkr(provider_name)


def build_market_data_provider(
    *,
    rt: Any | None = None,
    provider_name: str | None = None,
) -> MarketDataProvider:
    """
    Build the active market data provider.

    IBKR mode wraps the existing RealTimeIB object.
    CSV mode reads from local cache/replay files.
    Tradier mode uses TRADIER_ACCESS_TOKEN and TRADIER_ENV.
    """
    provider = str(provider_name or get_market_data_provider_name()).strip().lower()

    if provider in {"ibkr", "ib", "interactive_brokers", "interactive-brokers"}:
        if rt is None:
            raise ValueError("IBKR market data provider requires rt=RealTimeIB(...).")
        return IBKRMarketDataProvider(rt)

    if provider in {"csv", "local", "file", "files"}:
        root_dir = os.getenv("CSV_MARKET_DATA_ROOT", "cache/replay")
        return CSVMarketDataProvider(root_dir=root_dir)

    if provider == "tradier":
        if TradierMarketDataProvider is None:
            raise ImportError(
                "TradierMarketDataProvider could not be imported. "
                "Check Live/services/market_data/tradier_provider.py."
            )

        return TradierMarketDataProvider(
            access_token=os.getenv("TRADIER_ACCESS_TOKEN", ""),
            environment=os.getenv("TRADIER_ENV", "sandbox"),
            timeout=float(os.getenv("TRADIER_TIMEOUT_SECONDS", "30")),
        )

    raise ValueError(
        f"Unsupported MARKET_DATA_PROVIDER={provider!r}. "
        "Supported providers: ibkr, csv, tradier."
    )


def describe_market_data_provider(provider: MarketDataProvider) -> dict[str, Any]:
    """
    Return lightweight provider metadata for diagnostics/UI.
    """
    return {
        "name": getattr(provider, "name", provider.__class__.__name__),
        "class": provider.__class__.__name__,
    }
