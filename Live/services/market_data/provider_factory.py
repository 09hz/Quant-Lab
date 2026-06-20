from __future__ import annotations

import os
from pathlib import Path

from services.market_data.base import MarketDataProvider
from services.market_data.csv_provider import CSVMarketDataProvider
from services.market_data.ibkr_provider import IBKRMarketDataProvider


def get_market_data_provider(
    *,
    rt=None,
    provider_name: str | None = None,
    csv_root_dir: str | Path | None = None,
) -> MarketDataProvider:
    """
    Build the configured market data provider.

    Environment:
        MARKET_DATA_PROVIDER=ibkr | csv
        CSV_MARKET_DATA_ROOT=cache/replay

    Patch 01 intentionally supports only IBKR and CSV. Tradier/Alpaca should
    be added later as separate provider classes.
    """
    name = str(
        provider_name
        or os.getenv("MARKET_DATA_PROVIDER")
        or "ibkr"
    ).lower().strip()

    if name in {"ibkr", "interactive_brokers", "interactive-brokers"}:
        if rt is None:
            raise ValueError("IBKR market data provider requires an existing RealTimeIB instance.")
        return IBKRMarketDataProvider(rt)

    if name in {"csv", "local", "parquet"}:
        return CSVMarketDataProvider(
            root_dir=csv_root_dir or os.getenv("CSV_MARKET_DATA_ROOT", "cache/replay"),
        )

    raise ValueError(
        f"Unsupported MARKET_DATA_PROVIDER={name!r}. "
        "Supported providers in patch 01: ibkr, csv."
    )
