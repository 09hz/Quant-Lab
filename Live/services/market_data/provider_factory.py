from __future__ import annotations

import os
from typing import Any

from services.market_data.csv_provider import CSVMarketDataProvider
from services.market_data.ibkr_provider import IBKRMarketDataProvider
from services.market_data.base import MarketDataProvider


SUPPORTED_MARKET_DATA_PROVIDERS = {"ibkr", "csv", "local"}


def get_market_data_provider_name(default: str = "ibkr") -> str:
    name = os.getenv("MARKET_DATA_PROVIDER", default)
    name = str(name or default).strip().lower()

    if name == "local":
        return "csv"

    if name not in SUPPORTED_MARKET_DATA_PROVIDERS:
        print(
            f"[MARKET DATA] Unsupported MARKET_DATA_PROVIDER={name!r}; using {default!r}.",
            flush=True,
        )
        return str(default or "ibkr").strip().lower()

    return name


def build_market_data_provider(
    *,
    rt: Any | None = None,
    default: str = "ibkr",
) -> MarketDataProvider:
    """
    Build the active market data provider.

    Environment:
        MARKET_DATA_PROVIDER=ibkr  # default
        MARKET_DATA_PROVIDER=csv
        CSV_MARKET_DATA_ROOT=cache/replay
    """
    provider_name = get_market_data_provider_name(default=default)

    if provider_name == "ibkr":
        if rt is None:
            raise ValueError("IBKR provider requires rt=RealTimeIB(...)")
        return IBKRMarketDataProvider(rt)

    if provider_name in {"csv", "local"}:
        root_dir = os.getenv("CSV_MARKET_DATA_ROOT", "cache/replay")
        return CSVMarketDataProvider(root_dir=root_dir)

    raise ValueError(f"Unsupported market data provider: {provider_name}")
