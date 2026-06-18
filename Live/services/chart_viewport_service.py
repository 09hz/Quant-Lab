from __future__ import annotations

from datetime import timedelta
from typing import Any

import pandas as pd
from dash import no_update


class ChartViewportService:
    """
    Explicit viewport state model for chart pan/zoom/follow behavior.

    This keeps replay follow-mode, range buttons, and user zoom from fighting
    each other.
    """

    VALID_RANGE_KEYS = {"1D", "1W", "1M", "3M", "1Y", "5Y", "MAX"}

    RANGE_DAYS = {
        "1D": 1,
        "1W": 7,
        "1M": 30,
        "3M": 90,
        "1Y": 365,
        "5Y": 365 * 5,
    }

    def default_state(self, range_key: str = "1D") -> dict[str, Any]:
        return {
            "mode": "follow",
            "range_key": self.safe_range_key(range_key),
            "x_range": None,
            "y_mode": "auto_visible",
            "y_range": None,
        }

    def safe_range_key(self, value: str | None, default: str = "1D") -> str:
        value = str(value or default).upper()
        return value if value in self.VALID_RANGE_KEYS else default

    def range_key_from_button(
        self,
        trigger_id: str | None,
        prefix: str,
        default: str = "1D",
    ) -> str:
        if not trigger_id:
            return default

        raw = str(trigger_id).replace(prefix, "").lower()
        mapping = {
            "1d": "1D",
            "1w": "1W",
            "1m": "1M",
            "3m": "3M",
            "1y": "1Y",
            "5y": "5Y",
            "max": "MAX",
        }
        return mapping.get(raw, default)

    def parse_relayout(self, relayout_data):
        if not relayout_data:
            return no_update

        if (
            relayout_data.get("xaxis.autorange") is True
            or relayout_data.get("yaxis.autorange") is True
            or relayout_data.get("autosize") is True
        ):
            return self.default_state()

        x0 = relayout_data.get("xaxis.range[0]")
        x1 = relayout_data.get("xaxis.range[1]")
        y0 = relayout_data.get("yaxis.range[0]")
        y1 = relayout_data.get("yaxis.range[1]")

        if x0 is not None and x1 is not None:
            return {
                "mode": "manual",
                "range_key": "1D",
                "x_range": [x0, x1],
                "y_mode": "manual" if y0 is not None and y1 is not None else "auto_visible",
                "y_range": [y0, y1] if y0 is not None and y1 is not None else None,
            }

        if y0 is not None and y1 is not None:
            return {
                "mode": "manual",
                "range_key": "1D",
                "x_range": None,
                "y_mode": "manual",
                "y_range": [y0, y1],
            }

        return no_update

    def visible_x_range(self, bars: pd.DataFrame, state: dict | None):
        if bars is None or bars.empty or "time" not in bars.columns:
            return None

        state = state or self.default_state()
        mode = state.get("mode", "follow")

        if mode == "manual":
            return state.get("x_range")

        range_key = self.safe_range_key(state.get("range_key"), "1D")
        times = pd.to_datetime(bars["time"], errors="coerce").dropna()

        if times.empty:
            return None

        end_time = times.max()

        if range_key == "MAX":
            start_time = times.min()
        else:
            days = self.RANGE_DAYS.get(range_key, 1)
            start_time = max(end_time - timedelta(days=days), times.min())

        return [start_time, end_time]

    def apply_to_figure(self, fig, bars: pd.DataFrame, state: dict | None, default_range="1D"):
        state = state or self.default_state(default_range)

        if bars is None or bars.empty:
            return fig

        mode = state.get("mode", "follow")
        x_range = self.visible_x_range(bars, state)

        if x_range:
            fig.update_xaxes(range=x_range, fixedrange=False)

        if mode == "manual" and state.get("y_range"):
            fig.update_yaxes(range=state.get("y_range"), fixedrange=False)
            return fig

        return self.fit_y_axis_to_visible_bars(fig, bars, x_range)

    def fit_y_axis_to_visible_bars(self, fig, bars: pd.DataFrame, x_range=None):
        if bars is None or bars.empty:
            return fig

        df = bars.copy()
        if "time" not in df.columns:
            return fig

        df["time"] = pd.to_datetime(df["time"], errors="coerce")
        df["high"] = pd.to_numeric(df.get("high"), errors="coerce")
        df["low"] = pd.to_numeric(df.get("low"), errors="coerce")
        df = df.dropna(subset=["time", "high", "low"])

        if df.empty:
            return fig

        visible = df
        if x_range:
            x0 = pd.to_datetime(x_range[0], errors="coerce")
            x1 = pd.to_datetime(x_range[1], errors="coerce")
            if pd.notna(x0) and pd.notna(x1):
                visible = df[(df["time"] >= x0) & (df["time"] <= x1)]

        if visible.empty:
            visible = df.tail(100)

        high = float(visible["high"].max())
        low = float(visible["low"].min())

        if high <= low:
            pad = max(abs(high) * 0.005, 0.01)
        else:
            pad = (high - low) * 0.08

        fig.update_yaxes(range=[low - pad, high + pad], fixedrange=False)
        return fig
