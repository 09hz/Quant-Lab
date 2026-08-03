from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
import csv
import hashlib
import math
import shutil


@dataclass
class BootstrapResult:
    symbol: str
    csv_path: str
    source: str
    row_count: int
    first_date: str = ""
    last_date: str = ""
    message: str = ""
    warnings: list[str] | None = None
    requested_start: str = ""
    requested_end: str = ""
    coverage_ok: bool = False
    data_quality_ok: bool = False
    duplicate_rows: int = 0
    invalid_ohlc_rows: int = 0
    large_gap_count: int = 0
    data_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def market_bars_dir(live_root: Path) -> Path:
    return live_root / "data" / "market_bars"


def output_csv_path(live_root: Path, symbol: str, timeframe: str = "1d") -> Path:
    safe_symbol = "".join(ch for ch in symbol.upper().strip() if ch.isalnum() or ch in ("-", "_")) or "SYMBOL"
    safe_timeframe = "".join(ch for ch in timeframe.lower().strip() if ch.isalnum() or ch in ("-", "_")) or "1d"
    return market_bars_dir(live_root) / f"{safe_symbol}_{safe_timeframe}.csv"


def _parse_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        try:
            return datetime.strptime(text[:10], "%Y-%m-%d")
        except Exception:
            return None


def _content_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _analyze_csv(path: Path, start: str = "", end: str = "", timeframe: str = "1d") -> dict[str, Any]:
    warnings: list[str] = []
    row_count = 0
    duplicate_rows = 0
    invalid_ohlc_rows = 0
    timestamps: list[datetime] = []
    seen_timestamps: set[datetime] = set()

    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        lowered = {str(column).strip().lower(): column for column in (reader.fieldnames or [])}
        date_col = next((lowered[key] for key in ("date", "datetime", "timestamp", "time") if key in lowered), None)
        price_cols = {
            name: lowered.get(name)
            for name in ("open", "high", "low", "close")
        }

        if date_col is None:
            warnings.append("Missing date/time column.")
        if any(column is None for column in price_cols.values()):
            warnings.append("Missing one or more OHLC columns.")

        for row in reader:
            row_count += 1
            timestamp = _parse_datetime(row.get(date_col, "") if date_col else "")
            if timestamp is not None:
                if timestamp in seen_timestamps:
                    duplicate_rows += 1
                else:
                    seen_timestamps.add(timestamp)
                    timestamps.append(timestamp)

            try:
                open_price = float(row.get(price_cols["open"], ""))
                high_price = float(row.get(price_cols["high"], ""))
                low_price = float(row.get(price_cols["low"], ""))
                close_price = float(row.get(price_cols["close"], ""))
                values = (open_price, high_price, low_price, close_price)
                valid = all(math.isfinite(value) and value > 0 for value in values)
                valid = valid and high_price >= max(open_price, close_price, low_price)
                valid = valid and low_price <= min(open_price, close_price, high_price)
                if not valid:
                    invalid_ohlc_rows += 1
            except Exception:
                invalid_ohlc_rows += 1

    timestamps.sort()
    first_timestamp = timestamps[0] if timestamps else None
    last_timestamp = timestamps[-1] if timestamps else None
    daily = str(timeframe or "").lower().strip() in {"1d", "d", "day", "daily"}
    maximum_gap = timedelta(days=7 if daily else 4)
    large_gap_count = sum(
        1
        for previous, current in zip(timestamps, timestamps[1:])
        if current - previous > maximum_gap
    )

    requested_start = _parse_datetime(start)
    requested_end = _parse_datetime(end)
    tolerance = timedelta(days=4 if daily else 1)
    start_ok = requested_start is None or (
        first_timestamp is not None and first_timestamp <= requested_start + tolerance
    )
    end_ok = requested_end is None or (
        last_timestamp is not None and last_timestamp >= requested_end - tolerance
    )
    coverage_ok = bool(row_count > 0 and timestamps and start_ok and end_ok)
    data_quality_ok = bool(
        row_count > 0
        and len(timestamps) > 0
        and duplicate_rows == 0
        and invalid_ohlc_rows == 0
        and large_gap_count == 0
    )

    if not start_ok:
        warnings.append(f"Requested start {start!r} precedes available data {first_timestamp}.")
    if not end_ok:
        warnings.append(f"Requested end {end!r} exceeds available data {last_timestamp}.")
    if duplicate_rows:
        warnings.append(f"Detected {duplicate_rows} duplicate timestamp rows.")
    if invalid_ohlc_rows:
        warnings.append(f"Detected {invalid_ohlc_rows} invalid OHLC rows.")
    if large_gap_count:
        warnings.append(f"Detected {large_gap_count} unexpectedly large time gaps.")

    return {
        "row_count": row_count,
        "first_date": first_timestamp.isoformat(sep=" ") if first_timestamp else "",
        "last_date": last_timestamp.isoformat(sep=" ") if last_timestamp else "",
        "coverage_ok": coverage_ok,
        "data_quality_ok": data_quality_ok,
        "duplicate_rows": duplicate_rows,
        "invalid_ohlc_rows": invalid_ohlc_rows,
        "large_gap_count": large_gap_count,
        "data_hash": _content_hash(path),
        "warnings": warnings,
    }


def _build_result(
    *,
    path: Path,
    symbol: str,
    source: str,
    message: str,
    start: str = "",
    end: str = "",
    timeframe: str = "1d",
    warnings: list[str] | None = None,
) -> BootstrapResult:
    profile = _analyze_csv(path, start=start, end=end, timeframe=timeframe)
    return BootstrapResult(
        symbol=symbol.upper(),
        csv_path=str(path),
        source=source,
        row_count=profile["row_count"],
        first_date=profile["first_date"],
        last_date=profile["last_date"],
        message=message,
        warnings=list(warnings or []) + profile["warnings"],
        requested_start=start or "",
        requested_end=end or "",
        coverage_ok=profile["coverage_ok"],
        data_quality_ok=profile["data_quality_ok"],
        duplicate_rows=profile["duplicate_rows"],
        invalid_ohlc_rows=profile["invalid_ohlc_rows"],
        large_gap_count=profile["large_gap_count"],
        data_hash=profile["data_hash"],
    )


def _profile_csv(path: Path) -> tuple[int, str, str]:
    try:
        profile = _analyze_csv(path)
        return profile["row_count"], profile["first_date"], profile["last_date"]
    except Exception:
        return 0, "", ""


def _candidate_local_paths(live_root: Path, symbol: str, timeframe: str = "1d") -> list[Path]:
    symbol = symbol.upper().strip()
    names = [
        f"{symbol}_{timeframe}.csv",
        f"{symbol}-{timeframe}.csv",
        f"{symbol}.csv",
        f"{symbol.lower()}_{timeframe}.csv",
        f"{symbol.lower()}-{timeframe}.csv",
        f"{symbol.lower()}.csv",
    ]
    roots = [
        market_bars_dir(live_root),
        live_root / "data" / "bars",
        live_root / "data" / "market_data",
        live_root / "data" / "historical_bars",
        live_root / "data" / "csv",
        live_root / "data",
    ]
    return [root / name for root in roots for name in names]


def find_local_bars_csv(
    live_root: Path,
    symbol: str,
    timeframe: str = "1d",
    start: str = "",
    end: str = "",
) -> Path | None:
    candidates = _candidate_local_paths(live_root, symbol=symbol, timeframe=timeframe)
    fallback: Path | None = None

    for root in [
        market_bars_dir(live_root),
        live_root / "data" / "bars",
        live_root / "data" / "market_data",
        live_root / "data" / "historical_bars",
    ]:
        if root.exists() and root.is_dir():
            candidates.extend(sorted(root.glob(f"*{symbol.upper()}*.csv")))
            candidates.extend(sorted(root.glob(f"*{symbol.lower()}*.csv")))

    for path in dict.fromkeys(candidates):
        if path.exists() and path.is_file():
            profile = _analyze_csv(path, start=start, end=end, timeframe=timeframe)
            if profile["row_count"] > 0 and fallback is None:
                fallback = path
            if profile["coverage_ok"] and profile["data_quality_ok"]:
                return path

    return fallback


def copy_local_bars_to_market_dir(
    live_root: Path,
    source_path: Path,
    symbol: str,
    timeframe: str = "1d",
    start: str = "",
    end: str = "",
) -> BootstrapResult:
    dest = output_csv_path(live_root, symbol=symbol, timeframe=timeframe)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if source_path.resolve() != dest.resolve():
        shutil.copyfile(source_path, dest)
    return _build_result(
        path=dest,
        symbol=symbol,
        source=f"local_cache:{source_path}",
        message="Found local CSV bars and copied them to Live/data/market_bars.",
        start=start,
        end=end,
        timeframe=timeframe,
    )


def fetch_provider_to_csv(
    live_root: Path,
    provider: Any,
    symbol: str,
    start: str,
    end: str,
    timeframe: str = "1d",
) -> BootstrapResult:
    from services.market_data.base import normalize_ohlcv

    bars = normalize_ohlcv(
        provider.get_history(
            symbol=symbol,
            timeframe=timeframe,
            start=start or None,
            end=end or None,
        )
    )
    if bars.empty:
        raise RuntimeError(f"MarketDataProvider returned no bars for {symbol}.")

    dest = output_csv_path(live_root, symbol=symbol, timeframe=timeframe)
    dest.parent.mkdir(parents=True, exist_ok=True)
    output = bars.rename(columns={"time": "date"}).copy()
    output.to_csv(dest, index=False)
    provider_name = str(getattr(provider, "name", provider.__class__.__name__) or "unknown")
    return _build_result(
        path=dest,
        symbol=symbol,
        source=f"provider:{provider_name}",
        message="Loaded historical bars through the configured MarketDataProvider and cached them for Auto Lab.",
        start=start,
        end=end,
        timeframe=timeframe,
        warnings=["Simulation/research only; provider data was normalized before use."],
    )


def download_yfinance_to_csv(
    live_root: Path,
    symbol: str,
    start: str,
    end: str,
    timeframe: str = "1d",
) -> BootstrapResult:
    try:
        import yfinance as yf
    except Exception as exc:
        raise RuntimeError(
            "yfinance is not installed or could not be imported. "
            "Install it in your venv with: python -m pip install yfinance"
        ) from exc

    dest = output_csv_path(live_root, symbol=symbol, timeframe=timeframe)
    dest.parent.mkdir(parents=True, exist_ok=True)

    interval = "1d" if timeframe.lower() in {"1d", "d", "daily"} else timeframe
    df = yf.download(
        tickers=symbol,
        start=start or None,
        end=end or None,
        interval=interval,
        auto_adjust=True,
        progress=False,
        threads=False,
    )

    if df is None or getattr(df, "empty", True):
        raise RuntimeError(f"yfinance returned no data for {symbol} start={start!r} end={end!r} interval={interval!r}")

    try:
        if getattr(df.columns, "nlevels", 1) > 1:
            df.columns = [str(col[0]) for col in df.columns]
    except Exception:
        pass

    df = df.reset_index()
    col_map = {}
    for col in df.columns:
        key = str(col).strip().lower()
        if key in {"date", "datetime"}:
            col_map[col] = "date"
        elif key == "open":
            col_map[col] = "open"
        elif key == "high":
            col_map[col] = "high"
        elif key == "low":
            col_map[col] = "low"
        elif key in {"close", "adj close"} and "close" not in col_map.values():
            col_map[col] = "close"
        elif key == "volume":
            col_map[col] = "volume"

    df = df.rename(columns=col_map)
    required = ["date", "open", "high", "low", "close"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise RuntimeError(f"Downloaded yfinance data missing required columns: {missing}; columns={list(df.columns)}")

    if "volume" not in df.columns:
        df["volume"] = 0

    df = df[["date", "open", "high", "low", "close", "volume"]].copy()
    df.to_csv(dest, index=False)

    return _build_result(
        path=dest,
        symbol=symbol,
        source="yfinance",
        message="Downloaded public historical bars with yfinance and saved CSV.",
        start=start,
        end=end,
        timeframe=timeframe,
        warnings=[
            "Data source is third-party/public-market data; validate before research conclusions.",
            "Yahoo prices use auto-adjustment for splits and distributions.",
            "Simulation/research only; not live trading advice.",
        ],
    )


def bootstrap_bars_csv(
    live_root: Path,
    symbol: str,
    start: str = "",
    end: str = "",
    timeframe: str = "1d",
    prefer_local: bool = True,
    allow_yfinance: bool = True,
    provider: Any | None = None,
) -> BootstrapResult:
    symbol = symbol.upper().strip() or "AMD"
    local_result: BootstrapResult | None = None

    if prefer_local:
        existing = find_local_bars_csv(
            live_root,
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
        )
        if existing:
            local_result = copy_local_bars_to_market_dir(
                live_root,
                existing,
                symbol=symbol,
                timeframe=timeframe,
                start=start,
                end=end,
            )
            if local_result.coverage_ok and local_result.data_quality_ok:
                return local_result

    if provider is not None:
        provider_result = fetch_provider_to_csv(
            live_root,
            provider=provider,
            symbol=symbol,
            start=start,
            end=end,
            timeframe=timeframe,
        )
        if provider_result.coverage_ok and provider_result.data_quality_ok:
            return provider_result
        raise ValueError(
            f"Provider bars failed coverage or quality checks for {symbol}: "
            f"coverage_ok={provider_result.coverage_ok}, data_quality_ok={provider_result.data_quality_ok}, "
            f"warnings={provider_result.warnings}"
        )

    if allow_yfinance:
        downloaded = download_yfinance_to_csv(live_root, symbol=symbol, start=start, end=end, timeframe=timeframe)
        if downloaded.coverage_ok and downloaded.data_quality_ok:
            return downloaded
        raise ValueError(
            f"Downloaded bars failed coverage or quality checks for {symbol}: "
            f"coverage_ok={downloaded.coverage_ok}, data_quality_ok={downloaded.data_quality_ok}, "
            f"warnings={downloaded.warnings}"
        )

    if local_result is not None:
        raise ValueError(
            f"Local bars failed coverage or quality checks for {symbol}: "
            f"coverage_ok={local_result.coverage_ok}, data_quality_ok={local_result.data_quality_ok}, "
            f"warnings={local_result.warnings}"
        )

    raise FileNotFoundError(
        f"No local CSV bars found for {symbol}, and yfinance fallback is disabled. "
        f"Expected output path would be: {output_csv_path(live_root, symbol=symbol, timeframe=timeframe)}"
    )
