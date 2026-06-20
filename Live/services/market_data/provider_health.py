from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from services.market_data.base import OHLCV_COLUMNS, normalize_ohlcv


@dataclass
class ProviderHealthResult:
    provider_name: str
    symbol: str
    timeframe: str
    ok: bool
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_lines(self) -> list[str]:
        lines = [
            "Market Data Provider Check",
            f"Provider: {self.provider_name}",
            f"Symbol: {self.symbol}",
            f"Timeframe: {self.timeframe}",
            f"Status: {'OK' if self.ok else 'FAILED'}",
            f"Message: {self.status}",
        ]

        if self.details:
            lines.append("")
            lines.append("Details:")
            for key, value in self.details.items():
                lines.append(f"  {key}: {value}")

        if self.warnings:
            lines.append("")
            lines.append("Warnings:")
            for warning in self.warnings:
                lines.append(f"  - {warning}")

        if self.errors:
            lines.append("")
            lines.append("Errors:")
            for error in self.errors:
                lines.append(f"  - {error}")

        return lines


def _provider_name(provider) -> str:
    return str(getattr(provider, "name", provider.__class__.__name__) or "unknown")


def _safe_len(value) -> int:
    try:
        return int(len(value))
    except Exception:
        return 0


def check_provider_health(
    provider,
    *,
    symbol: str = "MSFT",
    timeframe: str = "1 min",
    fetch_history: bool = True,
    fetch_snapshot: bool = True,
    require_snapshot: bool = False,
) -> ProviderHealthResult:
    """
    Smoke-check a MarketDataProvider without needing Dash.

    Snapshot failures are warnings by default because IBKR can raise
    "No loaded state" when no symbol has been subscribed/loaded in this
    diagnostic process.
    """
    errors: list[str] = []
    warnings: list[str] = []
    details: dict[str, Any] = {}

    provider_name = _provider_name(provider)

    if provider is None:
        return ProviderHealthResult(
            provider_name="none",
            symbol=symbol,
            timeframe=timeframe,
            ok=False,
            status="No provider object was supplied.",
            errors=["provider is None"],
        )

    try:
        safe_symbol = provider.sanitize_symbol(symbol)
    except Exception as exc:
        safe_symbol = str(symbol or "").upper().strip()
        errors.append(f"sanitize_symbol failed: {exc}")

    details["sanitized_symbol"] = safe_symbol

    try:
        options = provider.get_symbol_options()
        details["symbol_options_count"] = _safe_len(options)
    except Exception as exc:
        warnings.append(f"get_symbol_options failed: {exc}")

    if fetch_history:
        try:
            bars = provider.get_history(
                symbol=safe_symbol,
                timeframe=timeframe,
            )
            normalized = normalize_ohlcv(bars)

            details["history_rows"] = len(normalized)
            details["history_columns"] = ", ".join(list(normalized.columns))
            details["required_columns_present"] = all(
                col in normalized.columns for col in OHLCV_COLUMNS
            )

            if normalized.empty:
                warnings.append(
                    "History returned no bars. This may be normal for CSV mode "
                    "if no local data exists, or for a provider without an active session."
                )
            else:
                details["first_bar"] = str(normalized["time"].iloc[0])
                details["last_bar"] = str(normalized["time"].iloc[-1])

        except Exception as exc:
            errors.append(f"get_history failed: {exc}")
    else:
        details["history_check"] = "skipped"

    if fetch_snapshot:
        try:
            snapshot = provider.get_snapshot(safe_symbol, timeframe)
            details["snapshot_type"] = snapshot.__class__.__name__

            last = getattr(snapshot, "last", None)
            if last is not None:
                details["snapshot_last"] = last

            updated_at = getattr(snapshot, "updated_at", None)
            if updated_at is not None:
                details["snapshot_updated_at"] = updated_at

            bars = getattr(snapshot, "bars", None)
            details["snapshot_bars"] = _safe_len(bars)

        except Exception as exc:
            message = (
                f"get_snapshot failed: {exc}. "
                "If this is IBKR and no symbol was started/subscribed in this "
                "diagnostic process, this is expected."
            )
            if require_snapshot:
                errors.append(message)
            else:
                warnings.append(message)
                details["snapshot_check"] = "non-fatal warning"
    else:
        details["snapshot_check"] = "skipped"

    ok = len(errors) == 0
    if ok and warnings:
        status = "Provider health check passed with warnings."
    elif ok:
        status = "Provider health check passed."
    else:
        status = "Provider health check completed with issues."

    details["checked_at"] = datetime.now().isoformat(timespec="seconds")

    return ProviderHealthResult(
        provider_name=provider_name,
        symbol=safe_symbol,
        timeframe=timeframe,
        ok=ok,
        status=status,
        details=details,
        warnings=warnings,
        errors=errors,
    )
