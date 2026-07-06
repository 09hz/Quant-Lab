from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
import csv
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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def market_bars_dir(live_root: Path) -> Path:
    return live_root / "data" / "market_bars"


def output_csv_path(live_root: Path, symbol: str, timeframe: str = "1d") -> Path:
    safe_symbol = "".join(ch for ch in symbol.upper().strip() if ch.isalnum() or ch in ("-", "_")) or "SYMBOL"
    safe_timeframe = "".join(ch for ch in timeframe.lower().strip() if ch.isalnum() or ch in ("-", "_")) or "1d"
    return market_bars_dir(live_root) / f"{safe_symbol}_{safe_timeframe}.csv"


def _profile_csv(path: Path) -> tuple[int, str, str]:
    try:
        with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
            reader = csv.DictReader(handle)
            date_col = None
            if reader.fieldnames:
                lowered = {str(c).lower(): c for c in reader.fieldnames}
                for key in ("date", "datetime", "timestamp", "time"):
                    if key in lowered:
                        date_col = lowered[key]
                        break
            count = 0
            first = ""
            last = ""
            for row in reader:
                count += 1
                value = str(row.get(date_col, "") if date_col else "")
                if count == 1:
                    first = value
                last = value
            return count, first, last
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


def find_local_bars_csv(live_root: Path, symbol: str, timeframe: str = "1d") -> Path | None:
    for path in _candidate_local_paths(live_root, symbol=symbol, timeframe=timeframe):
        if path.exists() and path.is_file():
            rows, _, _ = _profile_csv(path)
            if rows > 0:
                return path

    for root in [
        market_bars_dir(live_root),
        live_root / "data" / "bars",
        live_root / "data" / "market_data",
        live_root / "data" / "historical_bars",
    ]:
        if not root.exists() or not root.is_dir():
            continue
        matches = sorted(root.glob(f"*{symbol.upper()}*.csv")) + sorted(root.glob(f"*{symbol.lower()}*.csv"))
        for match in matches:
            rows, _, _ = _profile_csv(match)
            if rows > 0:
                return match
    return None


def copy_local_bars_to_market_dir(live_root: Path, source_path: Path, symbol: str, timeframe: str = "1d") -> BootstrapResult:
    dest = output_csv_path(live_root, symbol=symbol, timeframe=timeframe)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if source_path.resolve() != dest.resolve():
        shutil.copyfile(source_path, dest)
    rows, first, last = _profile_csv(dest)
    return BootstrapResult(
        symbol=symbol.upper(),
        csv_path=str(dest),
        source=f"local_cache:{source_path}",
        row_count=rows,
        first_date=first,
        last_date=last,
        message="Found local CSV bars and copied them to Live/data/market_bars.",
        warnings=[],
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
        auto_adjust=False,
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

    rows, first, last = _profile_csv(dest)
    return BootstrapResult(
        symbol=symbol.upper(),
        csv_path=str(dest),
        source="yfinance",
        row_count=rows,
        first_date=first,
        last_date=last,
        message="Downloaded public historical bars with yfinance and saved CSV.",
        warnings=[
            "Data source is third-party/public-market data; validate before research conclusions.",
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
) -> BootstrapResult:
    symbol = symbol.upper().strip() or "AMD"

    if prefer_local:
        existing = find_local_bars_csv(live_root, symbol=symbol, timeframe=timeframe)
        if existing:
            return copy_local_bars_to_market_dir(live_root, existing, symbol=symbol, timeframe=timeframe)

    if allow_yfinance:
        return download_yfinance_to_csv(live_root, symbol=symbol, start=start, end=end, timeframe=timeframe)

    raise FileNotFoundError(
        f"No local CSV bars found for {symbol}, and yfinance fallback is disabled. "
        f"Expected output path would be: {output_csv_path(live_root, symbol=symbol, timeframe=timeframe)}"
    )
