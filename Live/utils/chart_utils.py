from __future__ import annotations

from datetime import datetime
from typing import Optional

import pandas as pd
import plotly.graph_objects as go


OHLCV_COLUMNS = ["time", "open", "high", "low", "close", "volume"]


def _to_tz_naive_timestamp(value) -> pd.Timestamp:
    ts = pd.Timestamp(value)

    if ts.tzinfo is not None:
        ts = ts.tz_localize(None)

    return ts


def normalize_history_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=OHLCV_COLUMNS)

    out = df.copy()

    rename_map = {}
    for src, dst in [
        ("date", "time"),
        ("Date", "time"),
        ("datetime", "time"),
        ("Datetime", "time"),
    ]:
        if src in out.columns and dst not in out.columns:
            rename_map[src] = dst

    if rename_map:
        out = out.rename(columns=rename_map)

    for col in OHLCV_COLUMNS:
        if col not in out.columns:
            if col == "volume":
                out[col] = 0
            else:
                raise ValueError(f"Missing required column: {col}")

    out = out[OHLCV_COLUMNS].copy()

    out["time"] = out["time"].apply(_to_tz_naive_timestamp)
    out["open"] = pd.to_numeric(out["open"], errors="coerce")
    out["high"] = pd.to_numeric(out["high"], errors="coerce")
    out["low"] = pd.to_numeric(out["low"], errors="coerce")
    out["close"] = pd.to_numeric(out["close"], errors="coerce")
    out["volume"] = pd.to_numeric(out["volume"], errors="coerce").fillna(0)

    out = out.dropna(subset=["time", "open", "high", "low", "close"])
    out = out.drop_duplicates(subset="time").sort_values("time").reset_index(drop=True)

    return out


def _floor_time_to_minute(ts: datetime) -> pd.Timestamp:
    return _to_tz_naive_timestamp(ts).floor("min")


def apply_tick_to_bars(bars, price, size=0, tick_time=None):
    import pandas as pd
    from datetime import datetime

    if bars is None or bars.empty or price is None:
        return bars

    df = bars.copy()

    if "time" not in df.columns:
        return df

    df["time"] = pd.to_datetime(df["time"], errors="coerce")
    df = df.dropna(subset=["time"])

    if df.empty:
        return df

    # Force tz-naive timestamps to avoid tz comparison errors.
    try:
        if getattr(df["time"].dt, "tz", None) is not None:
            df["time"] = df["time"].dt.tz_localize(None)
    except Exception:
        pass

    if tick_time is None:
        tick_time = datetime.now()

    tick_time = pd.to_datetime(tick_time, errors="coerce")

    if pd.isna(tick_time):
        return df

    try:
        if tick_time.tzinfo is not None:
            tick_time = tick_time.tz_localize(None)
    except Exception:
        try:
            tick_time = tick_time.replace(tzinfo=None)
        except Exception:
            pass

    price = float(price)
    size = float(size or 0)

    last_idx = df.index[-1]

    # Always patch the latest candle with the latest tick.
    old_high = float(df.loc[last_idx, "high"])
    old_low = float(df.loc[last_idx, "low"])

    df.loc[last_idx, "high"] = max(old_high, price)
    df.loc[last_idx, "low"] = min(old_low, price)
    df.loc[last_idx, "close"] = price

    if "volume" in df.columns and size > 0:
        try:
            df.loc[last_idx, "volume"] = float(df.loc[last_idx, "volume"] or 0) + size
        except Exception:
            pass

    return df

def resample_bars(bars: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    out = normalize_history_df(bars)
    if out.empty or timeframe == "1 min":
        return out

    rule_map = {
        "5 mins": "5min",
        "15 mins": "15min",
        "1 hour": "1h",
        "1 day": "1D",
    }

    if timeframe not in rule_map:
        raise ValueError(f"Unsupported timeframe: {timeframe}")

    out = out.set_index("time")
    resampled = out.resample(rule_map[timeframe]).agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
    )
    resampled = resampled.dropna(subset=["open", "high", "low", "close"]).reset_index()
    return resampled


def create_candlestick_figure(
    bars: pd.DataFrame,
    symbol: str,
    timeframe: str,
    current_price: Optional[float] = None,
) -> go.Figure:
    df = normalize_history_df(bars)

    # Prevent startup or very large datasets from causing unreadable initial
    # candle widths. The callbacks still control the actual visible range.
    if not df.empty:
        df = df.tail(1500).copy()

    fig = go.Figure()

    if not df.empty:
        fig.add_trace(
            go.Candlestick(
                x=df["time"],
                open=df["open"],
                high=df["high"],
                low=df["low"],
                close=df["close"],
                name=f"{symbol} {timeframe}",
                increasing_line_color="#22c55e",
                increasing_fillcolor="#22c55e",
                decreasing_line_color="#ef4444",
                decreasing_fillcolor="#ef4444",
                whiskerwidth=0.4,
            )
        )

        price_for_line = current_price
        if price_for_line is None:
            price_for_line = float(df.iloc[-1]["close"])

        fig.add_hline(
            y=float(price_for_line),
            line_width=1.2,
            line_dash="dot",
            line_color="#60a5fa",
            opacity=0.95,
            annotation_text=f"{float(price_for_line):,.2f}",
            annotation_position="right",
            annotation_font=dict(color="white", size=12),
            annotation_bgcolor="#2563eb",
            annotation_bordercolor="#60a5fa",
        )

    fig.update_layout(
        title=dict(
            text=f"{symbol} · {timeframe}",
            x=0.02,
            xanchor="left",
            font=dict(size=18, color="#f8fbff"),
        ),
        template="plotly_dark",
        paper_bgcolor="#071224",
        plot_bgcolor="#071224",
        font={"color": "#dbe7ff"},
        margin=dict(l=16, r=56, t=44, b=16),
        xaxis_rangeslider_visible=False,
        dragmode="pan",
        hovermode="x unified",
    )

    fig.update_xaxes(
        showgrid=True,
        gridcolor="rgba(255,255,255,0.05)",
        zeroline=False,
        showline=False,
        rangeslider_visible=False,
        fixedrange=False,
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor="rgba(255,255,255,0.05)",
        zeroline=False,
        showline=False,
        side="right",
        fixedrange=False,
    )

    return fig
