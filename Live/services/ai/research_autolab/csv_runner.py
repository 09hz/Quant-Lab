from __future__ import annotations

from pathlib import Path

import pandas as pd

from core.BackTestEngine import BackTestEngine
from core.StrategyEngine import StrategySignal

from .models import BacktestRequest, BacktestResult
from .safety import validate_backtest_request
from .sim_guard import assert_no_broker_modules_loaded, assert_simulation_only


REQUIRED_BAR_COLUMNS = {"open", "high", "low", "close"}


def _load_symbol_bars(bars_dir: Path, symbol: str) -> pd.DataFrame:
    symbol = str(symbol or "").upper().strip()
    candidates = [
        bars_dir / f"{symbol}.csv",
        bars_dir / f"{symbol.lower()}.csv",
        bars_dir / symbol / "bars.csv",
        bars_dir / symbol / "1_day.csv",
        bars_dir / symbol / "daily.csv",
    ]

    for path in candidates:
        if path.exists() and path.is_file():
            return _normalize_bars(pd.read_csv(path))

    raise FileNotFoundError(
        f"No CSV bars found for {symbol}. Tried: "
        + ", ".join(str(path) for path in candidates)
    )


def _normalize_bars(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])

    out = df.copy()
    if "time" not in out.columns:
        for candidate in ("date", "datetime", "timestamp"):
            if candidate in out.columns:
                out["time"] = out[candidate]
                break

    if "time" not in out.columns:
        out["time"] = pd.RangeIndex(start=0, stop=len(out), step=1)

    rename = {}
    for col in out.columns:
        low = str(col).lower().strip()
        if low in {"open", "high", "low", "close", "volume"} and col != low:
            rename[col] = low
    if rename:
        out = out.rename(columns=rename)

    missing = REQUIRED_BAR_COLUMNS.difference(out.columns)
    if missing:
        raise ValueError(f"Bars CSV missing columns: {sorted(missing)}")

    out["time"] = pd.to_datetime(out["time"], errors="coerce")
    for col in ["open", "high", "low", "close"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    if "volume" not in out.columns:
        out["volume"] = 0
    out["volume"] = pd.to_numeric(out["volume"], errors="coerce").fillna(0)

    out = out.dropna(subset=["time", "open", "high", "low", "close"]).copy()
    out = out.sort_values("time")
    return out[["time", "open", "high", "low", "close", "volume"]].reset_index(drop=True)


def _load_macro_series(macro_dir: Path | None) -> dict[str, pd.DataFrame]:
    if macro_dir is None:
        return {}

    macro_dir = Path(macro_dir)
    if not macro_dir.exists():
        return {}

    series: dict[str, pd.DataFrame] = {}
    for path in macro_dir.glob("*.csv"):
        sid = path.stem.upper()
        try:
            df = pd.read_csv(path)
            if "date" not in df.columns:
                for candidate in ("time", "observation_date", "DATE"):
                    if candidate in df.columns:
                        df["date"] = df[candidate]
                        break
            if "value" not in df.columns:
                for candidate in (sid, "VALUE", "close"):
                    if candidate in df.columns:
                        df["value"] = df[candidate]
                        break
            if "date" not in df.columns or "value" not in df.columns:
                continue
            df = df[["date", "value"]].copy()
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            df = df.dropna(subset=["date", "value"]).sort_values("date").reset_index(drop=True)
            if not df.empty:
                df["chg3"] = df["value"].diff(3)
                df["chg6"] = df["value"].diff(6)
                df["ma50"] = df["value"].rolling(50, min_periods=10).mean()
                series[sid] = df
        except Exception:
            continue
    return series


def _macro_snapshot(series: dict[str, pd.DataFrame], asof: pd.Timestamp) -> dict[str, dict[str, float]]:
    snap: dict[str, dict[str, float]] = {}
    if not series:
        return snap

    asof = pd.Timestamp(asof)
    for sid, df in series.items():
        sub = df[df["date"] <= asof]
        if sub.empty:
            continue
        row = sub.iloc[-1]
        snap[sid] = {
            "value": float(row.get("value", 0.0)),
            "chg3": float(row.get("chg3", 0.0)) if pd.notna(row.get("chg3", pd.NA)) else 0.0,
            "chg6": float(row.get("chg6", 0.0)) if pd.notna(row.get("chg6", pd.NA)) else 0.0,
            "ma50": float(row.get("ma50", 0.0)) if pd.notna(row.get("ma50", pd.NA)) else 0.0,
        }
    return snap


def _has(snap: dict[str, dict[str, float]], key: str) -> bool:
    return key in snap


def _chg3(snap: dict[str, dict[str, float]], key: str) -> float:
    return float(snap.get(key, {}).get("chg3", 0.0))


def _value(snap: dict[str, dict[str, float]], key: str) -> float:
    return float(snap.get(key, {}).get("value", 0.0))


def _ma50(snap: dict[str, dict[str, float]], key: str) -> float:
    return float(snap.get(key, {}).get("ma50", 0.0))


def _macro_allows_entry(request: BacktestRequest, snap: dict[str, dict[str, float]], require_macro_filters: bool) -> bool:
    if not require_macro_filters:
        return True

    hid = str(request.hypothesis_id or "")

    if hid == "rate_relief_tech":
        needed = ["DGS10", "VIXCLS"]
        if not all(_has(snap, x) for x in needed):
            return False
        equity_confirms = (
            (_has(snap, "NASDAQCOM") and _value(snap, "NASDAQCOM") >= _ma50(snap, "NASDAQCOM"))
            or (_has(snap, "SP500") and _value(snap, "SP500") >= _ma50(snap, "SP500"))
        )
        return _chg3(snap, "DGS10") <= 0 and _chg3(snap, "VIXCLS") <= 0 and equity_confirms

    if hid == "manufacturing_oil_relief":
        if not (_has(snap, "AMTMNO") and _has(snap, "DCOILWTICO")):
            return False
        production_confirms = (
            (_has(snap, "IPMAN") and _chg3(snap, "IPMAN") > 0)
            or (_has(snap, "INDPRO") and _chg3(snap, "INDPRO") > 0)
            or not (_has(snap, "IPMAN") or _has(snap, "INDPRO"))
        )
        return _chg3(snap, "AMTMNO") > 0 and _chg3(snap, "DCOILWTICO") < 0 and production_confirms

    if hid == "labor_sentiment_risk_filter":
        needed = ["PAYEMS", "UNRATE", "VIXCLS", "UMCSENT"]
        if not all(_has(snap, x) for x in needed):
            return False
        return (
            _chg3(snap, "PAYEMS") >= 0
            and _chg3(snap, "UNRATE") <= 0
            and _chg3(snap, "VIXCLS") <= 0
            and _chg3(snap, "UMCSENT") >= -5
        )

    return True


def _build_price_signals(
    bars: pd.DataFrame,
    request: BacktestRequest,
    *,
    macro_series: dict[str, pd.DataFrame] | None = None,
    require_macro_filters: bool = False,
) -> list[StrategySignal]:
    lookback = int(request.parameters.get("lookback", 50) or 50)
    holding_days = int(request.parameters.get("holding_days", 10) or 10)
    lookback = max(5, min(250, lookback))
    holding_days = max(1, min(90, holding_days))

    close = pd.to_numeric(bars["close"], errors="coerce")
    trend = close.rolling(lookback, min_periods=max(3, lookback // 3)).mean()
    times = bars["time"]

    signals: list[StrategySignal] = []
    in_position = False
    entry_idx: int | None = None
    macro_series = macro_series or {}

    for idx in range(len(bars)):
        price = close.iloc[idx]
        ma = trend.iloc[idx]
        if pd.isna(price) or pd.isna(ma):
            continue

        prev_price = close.iloc[idx - 1] if idx > 0 else pd.NA
        prev_ma = trend.iloc[idx - 1] if idx > 0 else pd.NA

        crossed_up = idx > 0 and pd.notna(prev_price) and pd.notna(prev_ma) and prev_price <= prev_ma and price > ma
        crossed_down = idx > 0 and pd.notna(prev_price) and pd.notna(prev_ma) and prev_price >= prev_ma and price < ma
        timed_exit = in_position and entry_idx is not None and (idx - entry_idx) >= holding_days
        signal_time = times.iloc[idx]

        if not in_position and crossed_up:
            snap = _macro_snapshot(macro_series, signal_time)
            if not _macro_allows_entry(request, snap, require_macro_filters=require_macro_filters):
                continue
            signals.append(
                StrategySignal(
                    index=int(idx),
                    time=signal_time,
                    side="BUY",
                    price=float(price),
                    rule=f"price crossed above {lookback}-bar trend; macro_filter={require_macro_filters}",
                )
            )
            in_position = True
            entry_idx = idx
            continue

        if in_position and (crossed_down or timed_exit):
            exit_reason = "timed exit" if timed_exit else f"price crossed below {lookback}-bar trend"
            signals.append(
                StrategySignal(
                    index=int(idx),
                    time=signal_time,
                    side="SELL",
                    price=float(price),
                    rule=exit_reason,
                )
            )
            in_position = False
            entry_idx = None

    return signals


def run_backtest_request_from_csv(
    request: BacktestRequest,
    *,
    bars_dir: str | Path,
    initial_cash: float = 100_000.0,
    quantity: int = 1,
    macro_dir: str | Path | None = None,
    require_macro_filters: bool = False,
) -> BacktestResult:
    assert_simulation_only()
    assert_no_broker_modules_loaded()

    errors = validate_backtest_request(request)
    if errors:
        return BacktestResult(request=request, metrics={}, notes=errors, passed_safety_checks=False)

    try:
        bars = _load_symbol_bars(Path(bars_dir), request.symbol)
        macro_series = _load_macro_series(Path(macro_dir)) if macro_dir else {}
        signals = _build_price_signals(
            bars,
            request,
            macro_series=macro_series,
            require_macro_filters=require_macro_filters,
        )
        result = BackTestEngine().run(
            bars=bars,
            signals=signals,
            initial_cash=initial_cash,
            quantity=quantity,
        )

        metrics = {
            "total_return_pct": float(result.total_return_pct),
            "total_pnl": float(result.total_pnl),
            "max_drawdown_pct": float(result.max_drawdown_pct),
            "win_rate_pct": float(result.win_rate_pct),
            "trade_count": float(result.trade_count),
            "final_equity": float(result.final_equity),
        }
        notes = list(result.errors or [])
        if require_macro_filters:
            notes.append("Macro filters applied at entry using latest FRED observation available at each bar date.")
        else:
            notes.append("Macro filters not enforced; this is a price-trend proxy baseline.")

        return BacktestResult(request=request, metrics=metrics, notes=notes, passed_safety_checks=True)
    except Exception as exc:
        return BacktestResult(request=request, metrics={}, notes=[f"CSV backtest failed: {exc}"], passed_safety_checks=False)
