from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import csv
import random
from datetime import datetime, timezone


@dataclass
class BarsPayload:
    symbol: str
    timeframe: str
    source_path: str
    row_count: int
    columns: list[str]
    engine_input: Any
    note: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "source_path": self.source_path,
            "row_count": self.row_count,
            "columns": list(self.columns),
            "note": self.note,
        }


def _repo_root(repo_root: str | Path) -> Path:
    return Path(repo_root).resolve()


def _candidate_csv_paths(repo_root: Path, symbol: str, timeframe: str | None = None) -> list[Path]:
    roots = [
        repo_root / "Live" / "data" / "catalog",
        repo_root / "Live" / "data",
        repo_root / "data",
        repo_root,
    ]
    symbol_lower = str(symbol or "").lower()
    timeframe_lower = str(timeframe or "").lower()

    candidates: list[tuple[int, float, Path]] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*.csv"):
            lower = str(path).lower()
            score = 0
            if symbol_lower and symbol_lower in lower:
                score += 10
            if timeframe_lower and timeframe_lower in lower:
                score += 2
            if "bars" in lower or "ohlcv" in lower or "prices" in lower or "price" in lower:
                score += 3
            try:
                mtime = path.stat().st_mtime
            except Exception:
                mtime = 0.0
            candidates.append((score, mtime, path))

    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item[2] for item in candidates]


def _coerce_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        text = str(value).strip().replace(",", "")
        if text == "":
            return default
        if text.lower() in {"nan", "none", "null"}:
            return default
        return float(text)
    except Exception:
        return default


def _normalize_row(row: dict[str, Any], symbol: str, index: int) -> dict[str, Any] | None:
    lower = {str(k).strip().lower(): v for k, v in row.items()}
    date_value = lower.get("date") or lower.get("datetime") or lower.get("timestamp") or lower.get("time") or index
    open_ = _coerce_float(lower.get("open"))
    high = _coerce_float(lower.get("high"))
    low = _coerce_float(lower.get("low"))
    close = _coerce_float(lower.get("close")) or _coerce_float(lower.get("adj_close")) or _coerce_float(lower.get("adjclose"))
    volume = _coerce_float(lower.get("volume"), 0.0) or 0.0

    if close is None:
        return None

    if open_ is None:
        open_ = close
    if high is None:
        high = max(open_, close)
    if low is None:
        low = min(open_, close)

    return {
        "symbol": str(lower.get("symbol") or symbol).upper(),
        "date": str(date_value),
        "open": float(open_),
        "high": float(high),
        "low": float(low),
        "close": float(close),
        "volume": float(volume),
    }


def _load_csv_rows(path: Path, symbol: str, max_rows: int = 5000) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            return rows

        for index, raw_row in enumerate(reader):
            if len(rows) >= max_rows:
                break
            row = _normalize_row(raw_row, symbol=symbol, index=index)
            if row is None:
                continue
            if row["symbol"] and row["symbol"].upper() != str(symbol).upper():
                if "symbol" in {str(k).lower() for k in raw_row.keys()}:
                    continue
            rows.append(row)
    return rows


def _synthetic_rows(symbol: str, timeframe: str, count: int = 250) -> list[dict[str, Any]]:
    seed = sum(ord(ch) for ch in f"{symbol}|{timeframe}")
    rng = random.Random(seed)
    price = 100.0 + (seed % 75)
    rows: list[dict[str, Any]] = []
    base_date = datetime(2020, 1, 1, tzinfo=timezone.utc)

    for idx in range(count):
        drift = 0.05 + (rng.random() - 0.5) * 1.8
        open_ = price
        close = max(1.0, price * (1.0 + drift / 100.0))
        high = max(open_, close) * (1.0 + rng.random() * 0.02)
        low = min(open_, close) * (1.0 - rng.random() * 0.02)
        volume = 1_000_000 + int(rng.random() * 500_000)
        rows.append(
            {
                "symbol": str(symbol).upper(),
                "date": f"{base_date.date().isoformat()}_{idx}",
                "open": round(open_, 4),
                "high": round(high, 4),
                "low": round(low, 4),
                "close": round(close, 4),
                "volume": volume,
            }
        )
        price = close
    return rows


def _rows_to_engine_input(rows: list[dict[str, Any]], symbol: str, timeframe: str, source_path: str, note: str) -> Any:
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "source_path": source_path,
        "note": note,
        "rows": rows,
    }


def build_engine_bars(repo_root: str | Path, symbol: str, timeframe: str = "1d", max_rows: int = 5000) -> BarsPayload:
    repo = _repo_root(repo_root)
    symbol = str(symbol or "").strip().upper()
    timeframe = str(timeframe or "1d").strip().lower()

    for path in _candidate_csv_paths(repo, symbol=symbol, timeframe=timeframe):
        try:
            rows = _load_csv_rows(path, symbol=symbol, max_rows=max_rows)
        except Exception:
            continue

        if rows:
            engine_input = _rows_to_engine_input(rows, symbol=symbol, timeframe=timeframe, source_path=str(path), note="loaded_from_csv")
            return BarsPayload(
                symbol=symbol,
                timeframe=timeframe,
                source_path=str(path),
                row_count=len(rows),
                columns=list(rows[0].keys()),
                engine_input=engine_input,
                note="loaded_from_csv",
            )

    rows = _synthetic_rows(symbol=symbol, timeframe=timeframe, count=min(max_rows, 250))
    engine_input = _rows_to_engine_input(rows, symbol=symbol, timeframe=timeframe, source_path="synthetic", note="synthetic_fallback")
    return BarsPayload(
        symbol=symbol,
        timeframe=timeframe,
        source_path="synthetic",
        row_count=len(rows),
        columns=list(rows[0].keys()) if rows else [],
        engine_input=engine_input,
        note="synthetic_fallback",
    )


def build_engine_bars_input(repo_root: str | Path, symbol: str, timeframe: str = "1d") -> Any:
    return build_engine_bars(repo_root=repo_root, symbol=symbol, timeframe=timeframe).engine_input
