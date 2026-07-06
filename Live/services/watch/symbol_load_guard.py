from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Tuple


@dataclass
class WatchSymbolLoadStatus:
    symbol: str
    timeframe: str
    state: str = "idle"
    requested_at: float = 0.0
    completed_at: float = 0.0
    error: str | None = None


class WatchSymbolLoadGuard:
    # Starts live symbol loads in a daemon background thread so Dash render
    # callbacks do not block on unloaded IBKR/provider symbols.

    def __init__(self, cooldown_seconds: float = 20.0) -> None:
        self.cooldown_seconds = float(cooldown_seconds)
        self._lock = threading.Lock()
        self._status: Dict[Tuple[int, str, str], WatchSymbolLoadStatus] = {}

    def _key(self, provider: Any, symbol: str, timeframe: str) -> Tuple[int, str, str]:
        return (id(provider), str(symbol or "").upper().strip(), str(timeframe or "1 min").strip())

    def get_status(self, provider: Any, symbol: str, timeframe: str = "1 min") -> WatchSymbolLoadStatus | None:
        key = self._key(provider, symbol, timeframe)
        with self._lock:
            return self._status.get(key)

    def request_async(self, provider: Any, symbol: str, timeframe: str = "1 min") -> WatchSymbolLoadStatus:
        symbol = str(symbol or "").upper().strip()
        timeframe = str(timeframe or "1 min").strip()
        key = self._key(provider, symbol, timeframe)
        now = time.time()

        with self._lock:
            existing = self._status.get(key)
            if existing is not None:
                if existing.state == "loading":
                    return existing

                recent = max(existing.requested_at or 0.0, existing.completed_at or 0.0)
                if recent and (now - recent) < self.cooldown_seconds:
                    return existing

            status = WatchSymbolLoadStatus(
                symbol=symbol,
                timeframe=timeframe,
                state="loading",
                requested_at=now,
                completed_at=0.0,
                error=None,
            )
            self._status[key] = status

        thread = threading.Thread(
            target=self._load_symbol,
            args=(provider, key, symbol, timeframe),
            name=f"watch-symbol-load-{symbol}-{timeframe}",
            daemon=True,
        )
        thread.start()
        return status

    def _load_symbol(self, provider: Any, key: Tuple[int, str, str], symbol: str, timeframe: str) -> None:
        error: str | None = None
        state = "loaded"

        try:
            request_symbol = getattr(provider, "request_symbol", None)
            if not callable(request_symbol):
                raise RuntimeError("market_data_provider has no request_symbol method")

            try:
                request_symbol(symbol, timeframe)
            except TypeError:
                request_symbol(symbol)
        except Exception as exc:
            error = str(exc)
            state = "failed"

        with self._lock:
            status = self._status.get(key)
            if status is None:
                status = WatchSymbolLoadStatus(symbol=symbol, timeframe=timeframe)
                self._status[key] = status

            status.state = state
            status.completed_at = time.time()
            status.error = error


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return float(raw)
    except Exception:
        return default


watch_symbol_load_guard = WatchSymbolLoadGuard(
    cooldown_seconds=_env_float("WATCH_SYMBOL_LOAD_COOLDOWN_SECONDS", 20.0)
)
