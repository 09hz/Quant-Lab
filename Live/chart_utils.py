from __future__ import annotations

from datetime import datetime
from typing import Optional

import pandas as pd
import plotly.graph_objects as go


def normalize_history_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])

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

    required = ["time", "open", "high", "low", "close", "volume"]
    for col in required:
        if col not in out.columns:
            if col == "volume":
                out[col] = 0
            else:
                raise ValueError(f"Missing required column: {col}")

    out = out[required].copy()
    out["time"] = pd.to_datetime(out["time"], errors="coerce")
    out["open"] = pd.to_numeric(out["open"], errors="coerce")
    out["high"] = pd.to_numeric(out["high"], errors="coerce")
    out["low"] = pd.to_numeric(out["low"], errors="coerce")
    out["close"] = pd.to_numeric(out["close"], errors="coerce")
    out["volume"] = pd.to_numeric(out["volume"], errors="coerce").fillna(0)

    out = out.dropna(subset=["time", "open", "high", "low", "close"])
    out = out.drop_duplicates(subset="time").sort_values("time").reset_index(drop=True)

    return out


def _floor_time_to_minute(ts: datetime) -> pd.Timestamp:
    return pd.Timestamp(ts).floor("min")


def apply_tick_to_bars(
    bars: pd.DataFrame,
    price: float,
    size: float,
    tick_time: Optional[datetime] = None,
) -> pd.DataFrame:
    if tick_time is None:
        tick_time = datetime.now()

    out = normalize_history_df(bars)
    bar_time = _floor_time_to_minute(tick_time)

    if out.empty:
        return pd.DataFrame(
            [
                {
                    "time": bar_time,
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "volume": size,
                }
            ]
        )

    last_idx = out.index[-1]
    last_bar_time = pd.Timestamp(out.loc[last_idx, "time"]).floor("min")

    if bar_time > last_bar_time:
        new_row = {
            "time": bar_time,
            "open": price,
            "high": price,
            "low": price,
            "close": price,
            "volume": size,
        }
        out = pd.concat([out, pd.DataFrame([new_row])], ignore_index=True)
        return out

    if bar_time == last_bar_time:
        out.loc[last_idx, "high"] = max(float(out.loc[last_idx, "high"]), price)
        out.loc[last_idx, "low"] = min(float(out.loc[last_idx, "low"]), price)
        out.loc[last_idx, "close"] = price
        out.loc[last_idx, "volume"] = float(out.loc[last_idx, "volume"]) + size
        return out

    return out


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


def create_candlestick_figure(bars: pd.DataFrame, symbol: str, timeframe: str) -> go.Figure:
    df = normalize_history_df(bars)

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

        last_price = float(df.iloc[-1]["close"])

        fig.add_hline(
            y=last_price,
            line_width=1.2,
            line_dash="dot",
            line_color="#60a5fa",
            opacity=0.95,
            annotation_text=f"{last_price:,.2f}",
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
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor="rgba(255,255,255,0.05)",
        zeroline=False,
        showline=False,
        side="right",
    )

    return fig