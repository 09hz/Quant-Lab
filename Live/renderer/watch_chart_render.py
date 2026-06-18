from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from utils.chart_utils import create_candlestick_figure


class WatchChartRenderer:
    """
    Plotly renderer for the Watch chart.

    This is intentionally a thin visual layer. It should not load replay data,
    mutate replay state, run strategy scripts, or touch paper broker state.
    """

    def empty_figure(self, title: str) -> go.Figure:
        fig = go.Figure()
        fig.update_layout(
            title=title,
            template="plotly_dark",
            paper_bgcolor="#0d1b4f",
            plot_bgcolor="#0d1b4f",
            font={"color": "#e8f1ff"},
            dragmode="pan",
            hovermode="x unified",
        )
        fig.update_xaxes(fixedrange=False, rangeslider_visible=False)
        fig.update_yaxes(fixedrange=False)
        return fig

    def base_candles(
        self,
        *,
        chart_bars: pd.DataFrame,
        symbol: str,
        display_timeframe: str,
        current_price: float | None,
    ) -> go.Figure:
        if chart_bars is None or chart_bars.empty:
            return self.empty_figure(
                f"{symbol} | {display_timeframe} | Waiting for chart data..."
            )

        return create_candlestick_figure(
            chart_bars,
            symbol,
            display_timeframe,
            current_price=current_price,
        )
