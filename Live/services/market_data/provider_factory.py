from __future__ import annotations

import os
from typing import Any

from services.market_data.base import MarketDataProvider
from services.market_data.csv_provider import CSVMarketDataProvider
from services.market_data.ibkr_provider import IBKRMarketDataProvider


IBKR_PROVIDER_NAMES = {"ibkr", "ib", "interactive_brokers", "interactive-brokers"}
CSV_PROVIDER_NAMES = {"csv", "local", "file", "files"}


def get_market_data_provider_name(default: str = "ibkr") -> str:
    """
    Return the configured market data provider name.

    This project is currently limited to:
        ibkr
        csv/local

    Tradier is intentionally disabled in this revert patch until the UI and
    provider layers are stable again.
    """
    return str(os.getenv("MARKET_DATA_PROVIDER", default) or default).strip().lower()


def should_start_ibkr(provider_name: str | None = None) -> bool:
    provider = str(provider_name or get_market_data_provider_name()).strip().lower()
    return provider in IBKR_PROVIDER_NAMES


def should_autostart_ibkr(provider_name: str | None = None) -> bool:
    """Compatibility alias used by older app code."""
    return should_start_ibkr(provider_name)


def should_start_ibkr_connection(provider_name: str | None = None) -> bool:
    """Compatibility alias used by older app code."""
    return should_start_ibkr(provider_name)


def build_market_data_provider(
    *,
    rt: Any | None = None,
    provider_name: str | None = None,
) -> MarketDataProvider:
    """
    Build the active market data provider.

    IBKR mode wraps the existing RealTimeIB object.
    CSV mode reads local cache/replay files.
    """
    provider = str(provider_name or get_market_data_provider_name()).strip().lower()

    if provider in IBKR_PROVIDER_NAMES:
        if rt is None:
            raise ValueError("IBKR market data provider requires rt=RealTimeIB(...).")
        return IBKRMarketDataProvider(rt)

    if provider in CSV_PROVIDER_NAMES:
        root_dir = os.getenv("CSV_MARKET_DATA_ROOT", "cache/replay")
        return CSVMarketDataProvider(root_dir=root_dir)

    if provider == "tradier":
        raise ValueError(
            "Tradier provider is currently disabled by the revert patch. "
            "Use MARKET_DATA_PROVIDER=ibkr or MARKET_DATA_PROVIDER=csv until "
            "Tradier is reintroduced in a clean provider-only patch."
        )

    raise ValueError(
        f"Unsupported MARKET_DATA_PROVIDER={provider!r}. "
        "Supported providers: ibkr, csv."
    )


def describe_market_data_provider(provider: MarketDataProvider) -> dict[str, Any]:
    return {
        "name": getattr(provider, "name", provider.__class__.__name__),
        "class": provider.__class__.__name__,
    }
