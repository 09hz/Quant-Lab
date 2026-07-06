from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from utils.chart_utils import create_candlestick_figure


class WatchChartRenderer:
    """
    Plotly renderers for the Watch chart.

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

    def _normalize_display_timeframe(self, display_timeframe: str | None) -> str:
        raw = str(display_timeframe or "1 min").strip().lower()
        raw = raw.replace("_", " ").replace("-", " ")
        raw = " ".join(raw.split())

        aliases = {
            "1d": "1 day",
            "1 day": "1 day",
            "day": "1 day",
            "daily": "1 day",
            "1h": "1 hour",
            "1hr": "1 hour",
            "1 hr": "1 hour",
            "1 hour": "1 hour",
            "hour": "1 hour",
            "1m": "1 min",
            "1 min": "1 min",
            "1 minute": "1 min",
        }
        return aliases.get(raw, raw or "1 min")

    def _is_daily_timeframe(self, display_timeframe: str | None) -> bool:
        return self._normalize_display_timeframe(display_timeframe) == "1 day"

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

        fig = create_candlestick_figure(
            chart_bars,
            symbol,
            display_timeframe,
            current_price=current_price,
        )

        if self._is_daily_timeframe(display_timeframe):
            # The shared candlestick helper is tuned for intraday charts. It may
            # apply intraday rangebreaks such as "hide outside 09:30-16:00".
            # Native daily IBKR bars are timestamped at 00:00:00, so those
            # rangebreaks can hide every daily candle.
            try:
                times = pd.Series(dtype="datetime64[ns]")
                if chart_bars is not None and not chart_bars.empty and "time" in chart_bars.columns:
                    times = pd.to_datetime(chart_bars["time"], errors="coerce").dropna()

                fig.update_xaxes(
                    type="date",
                    rangeslider_visible=False,
                    fixedrange=False,
                )
                fig.update_layout(xaxis_rangeslider_visible=False)

                # Force-clear existing rangebreaks. Plotly may retain
                # layout.xaxis.Rangebreak objects when update_xaxes(rangebreaks=[])
                # is used, so assign the property directly.
                try:
                    fig.layout.xaxis.rangebreaks = ()
                except Exception:
                    try:
                        fig.layout.xaxis.rangebreaks = []
                    except Exception:
                        pass

                if not times.empty:
                    # Pad daily charts so first/last candles are not clipped at
                    # the edges. This also makes small daily ranges visible.
                    x0 = times.min() - pd.Timedelta(days=1)
                    x1 = times.max() + pd.Timedelta(days=1)
                    fig.update_xaxes(range=[x0, x1])

                    # Some Plotly updates can restore/merge x-axis properties.
                    # Clear rangebreaks again after assigning the date range.
                    try:
                        fig.layout.xaxis.rangebreaks = ()
                    except Exception:
                        try:
                            fig.layout.xaxis.rangebreaks = []
                        except Exception:
                            pass

                print(
                    "[WATCH DAILY RENDER] "
                    f"symbol={symbol} timeframe={display_timeframe} "
                    f"rows={0 if chart_bars is None else len(chart_bars)} "
                    f"first={None if times.empty else times.iloc[0]} "
                    f"last={None if times.empty else times.iloc[-1]} "
                    "rangebreaks=off",
                    flush=True,
                )
            except Exception as daily_render_exc:
                print(f"[WATCH DAILY RENDER WARNING] {daily_render_exc}", flush=True)

        return fig

