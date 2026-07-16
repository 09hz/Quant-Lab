from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
import csv


@dataclass
class BarsDataProfile:
    source_path: str
    symbol: str
    data_mode: str
    row_count: int
    first_date: str
    last_date: str
    columns: list[str]
    normalized_columns: list[str]
    start_filter: str = ""
    end_filter: str = ""
    warnings: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _clean_col(value: str) -> str:
    return "".join(ch for ch in str(value).lower().strip() if ch.isalnum())


COLUMN_ALIASES = {
    "date": {"date", "datetime", "timestamp", "time", "barDate", "bardate"},
    "open": {"open", "o"},
    "high": {"high", "h"},
    "low": {"low", "l"},
    "close": {"close", "c", "adjclose", "adjustedclose"},
    "volume": {"volume", "vol", "v"},
}


def _detect_columns(columns: list[str]) -> tuple[dict[str, str], list[str]]:
    cleaned = {_clean_col(col): col for col in columns}
    detected: dict[str, str] = {}
    warnings: list[str] = []

    for target, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            key = _clean_col(alias)
            if key in cleaned:
                detected[target] = cleaned[key]
                break

    required = ["date", "open", "high", "low", "close"]
    missing = [name for name in required if name not in detected]
    if missing:
        raise ValueError(f"CSV is missing required OHLC/date columns: {missing}. Found columns: {columns}")

    if "volume" not in detected:
        warnings.append("Volume column missing; filled volume with 0.")

    return detected, warnings


def resolve_csv_path(csv_path: str | Path | None = None, bars_dir: str | Path | None = None, symbol: str = "") -> Path:
    if csv_path:
        path = Path(csv_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"CSV path does not exist: {path}")
        if not path.is_file():
            raise FileNotFoundError(f"CSV path is not a file: {path}")
        return path

    if not bars_dir:
        raise FileNotFoundError("Provide --csv-path or --bars-dir.")

    root = Path(bars_dir).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"Bars directory does not exist: {root}")

    sym = (symbol or "").strip()
    names = [
        f"{sym}.csv",
        f"{sym.upper()}.csv",
        f"{sym.lower()}.csv",
        f"{sym}_1d.csv",
        f"{sym.upper()}_1d.csv",
        f"{sym.lower()}_1d.csv",
        f"{sym}-1d.csv",
        f"{sym.upper()}-1d.csv",
        f"{sym.lower()}-1d.csv",
    ]
    for name in names:
        candidate = root / name
        if candidate.exists() and candidate.is_file():
            return candidate

    matches = sorted(root.glob(f"*{sym}*.csv")) if sym else sorted(root.glob("*.csv"))
    if matches:
        return matches[0]

    raise FileNotFoundError(f"No CSV found for symbol {symbol!r} in {root}")


def _load_with_pandas(path: Path, symbol: str, start: str = "", end: str = ""):
    import pandas as pd

    raw = pd.read_csv(path)
    if raw.empty:
        raise ValueError(f"CSV is empty: {path}")

    detected, warnings = _detect_columns([str(col) for col in raw.columns])
    df = raw.rename(columns={src: dst for dst, src in detected.items() if src in raw.columns}).copy()

    if "volume" not in df.columns:
        df["volume"] = 0

    normalized_cols = ["date", "open", "high", "low", "close", "volume"]
    df = df[normalized_cols].copy()

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close"])
    df["volume"] = df["volume"].fillna(0)

    if start:
        df = df[df["date"] >= pd.to_datetime(start)]
    if end:
        df = df[df["date"] <= pd.to_datetime(end)]

    df = df.sort_values("date").reset_index(drop=True)
    if df.empty:
        raise ValueError(f"No CSV rows remain after filtering start={start!r}, end={end!r}: {path}")

    df["symbol"] = symbol
    profile = BarsDataProfile(
        source_path=str(path),
        symbol=symbol,
        data_mode="csv_historical_bars",
        row_count=int(len(df)),
        first_date=str(df["date"].iloc[0].date()) if hasattr(df["date"].iloc[0], "date") else str(df["date"].iloc[0]),
        last_date=str(df["date"].iloc[-1].date()) if hasattr(df["date"].iloc[-1], "date") else str(df["date"].iloc[-1]),
        columns=[str(col) for col in raw.columns],
        normalized_columns=[str(col) for col in df.columns],
        start_filter=start or "",
        end_filter=end or "",
        warnings=warnings,
    )
    return df, profile


def _load_without_pandas(path: Path, symbol: str, start: str = "", end: str = ""):
    # Fallback mainly for diagnostics. Core engine usually has pandas available.
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames or []
        detected, warnings = _detect_columns(columns)
        rows = []
        for row in reader:
            normalized = {
                "date": row.get(detected["date"], ""),
                "open": float(row.get(detected["open"], 0) or 0),
                "high": float(row.get(detected["high"], 0) or 0),
                "low": float(row.get(detected["low"], 0) or 0),
                "close": float(row.get(detected["close"], 0) or 0),
                "volume": float(row.get(detected.get("volume", ""), 0) or 0) if detected.get("volume") else 0,
                "symbol": symbol,
            }
            if start and normalized["date"] < start:
                continue
            if end and normalized["date"] > end:
                continue
            rows.append(normalized)

    rows = sorted(rows, key=lambda item: item.get("date", ""))
    if not rows:
        raise ValueError(f"No CSV rows remain after filtering start={start!r}, end={end!r}: {path}")

    profile = BarsDataProfile(
        source_path=str(path),
        symbol=symbol,
        data_mode="csv_historical_bars",
        row_count=len(rows),
        first_date=str(rows[0].get("date", "")),
        last_date=str(rows[-1].get("date", "")),
        columns=columns,
        normalized_columns=["date", "open", "high", "low", "close", "volume", "symbol"],
        start_filter=start or "",
        end_filter=end or "",
        warnings=warnings + ["Pandas unavailable; loaded CSV as list of dicts."],
    )
    return rows, profile


def load_csv_bars(
    csv_path: str | Path | None = None,
    bars_dir: str | Path | None = None,
    symbol: str = "AMD",
    start: str = "",
    end: str = "",
):
    path = resolve_csv_path(csv_path=csv_path, bars_dir=bars_dir, symbol=symbol)
    try:
        return _load_with_pandas(path, symbol=symbol, start=start, end=end)
    except ImportError:
        return _load_without_pandas(path, symbol=symbol, start=start, end=end)


def write_sample_csv(path: Path, symbol: str = "AMD", days: int = 260) -> Path:
    """
    Write deterministic sample CSV for self-test.

    This is still synthetic data, but it exercises the CSV adapter path.
    """
    from .sample_data import make_sample_bars

    path.parent.mkdir(parents=True, exist_ok=True)
    bars = make_sample_bars(symbol=symbol, days=days)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["date", "open", "high", "low", "close", "volume"])
        writer.writeheader()
        for row in bars:
            writer.writerow({key: row.get(key) for key in ["date", "open", "high", "low", "close", "volume"]})
    return path
