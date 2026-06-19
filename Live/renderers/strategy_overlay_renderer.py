from __future__ import annotations

from types import SimpleNamespace
import copy
import time

import pandas as pd
import plotly.graph_objects as go


class StrategyOverlayRenderer:
    """
    Visual-only strategy overlay renderer for the Watch chart.

    This class does not run StrategyEngine and does not read/write replay,
    paper, or live-service state. It only receives an already-computed
    StrategyScriptResult and adds safe Plotly traces/shapes to a figure.
    """

    def __init__(
            self,
            *,
            replay_max_bars: int = 120,
            replay_max_signals: int = 15,
            slow_log_ms: float = 120.0,
    ):
        self.replay_max_bars = max(20, int(replay_max_bars or 120))
        self.replay_max_signals = max(0, int(replay_max_signals or 15))
        self.slow_log_ms = float(slow_log_ms or 120.0)

    def _clone_result_with_updates(self, result, **updates):
        """
        Return a result-like object with selected fields replaced.

        StrategyScriptResult has changed during development, so this helper
        supports mutable dataclasses, namedtuples, and plain objects. The
        overlay methods only need attribute access, so SimpleNamespace is a
        safe fallback when direct assignment is not possible.
        """
        if result is None:
            return result

        try:
            cloned = copy.copy(result)
        except Exception:
            cloned = result

        failed = False

        for key, value in updates.items():
            try:
                setattr(cloned, key, value)
            except Exception:
                failed = True
                break

        if not failed:
            return cloned

        try:
            return result._replace(**updates)
        except Exception:
            pass

        data = {}

        try:
            data.update(vars(result))
        except Exception:
            pass

        for name in (
            "lines",
            "signals",
            "errors",
            "backgrounds",
            "background_ranges",
            "plots",
        ):
            if name not in data and hasattr(result, name):
                try:
                    data[name] = getattr(result, name)
                except Exception:
                    pass

        data.update(updates)
        return SimpleNamespace(**data)

    def make_lightweight_replay_overlay(
            self,
            result,
            chart_bars: pd.DataFrame,
            max_bars: int | None = None,
            max_signals: int | None = None,
    ):
        """
        Build a lightweight StrategyScriptResult for active replay playback.

        StrategyEngine may calculate on the full loaded replay dataset, but
        Plotly should not redraw every historical indicator point and every
        signal marker on every replay tick.

        Important alignment rule:
        chart_bars represents the cursor-visible replay window. Indicator
        series may come from the full loaded dataset, so we first trim each
        series to len(chart_bars), then keep the recent tail. That avoids
        drawing future indicator values while replay is in the middle of a day.
        """
        max_bars = max(20, int(max_bars or self.replay_max_bars))
        max_signals = max(0, int(max_signals if max_signals is not None else self.replay_max_signals))

        if result is None or chart_bars is None or chart_bars.empty:
            return chart_bars, result

        if len(chart_bars) <= max_bars:
            return chart_bars, result

        recent_bars = chart_bars.tail(max_bars).reset_index(drop=True)
        cursor_len = len(chart_bars)

        light_lines = getattr(result, "lines", None)

        if isinstance(light_lines, dict):
            trimmed_lines = {}

            for name, series in light_lines.items():
                try:
                    s = pd.Series(series)
                    trimmed_lines[name] = (
                        s.iloc[: min(cursor_len, len(s))]
                        .tail(max_bars)
                        .reset_index(drop=True)
                    )
                except Exception:
                    trimmed_lines[name] = series

            light_lines = trimmed_lines

        recent_signals = []

        try:
            start_time = pd.to_datetime(
                recent_bars["time"].iloc[0],
                errors="coerce",
                format="mixed",
            )
            end_time = pd.to_datetime(
                recent_bars["time"].iloc[-1],
                errors="coerce",
                format="mixed",
            )

            for sig in getattr(result, "signals", []) or []:
                sig_time = pd.to_datetime(
                    getattr(sig, "time", None),
                    errors="coerce",
                    format="mixed",
                )

                if pd.notna(sig_time) and pd.notna(start_time) and pd.notna(end_time):
                    if start_time <= sig_time <= end_time:
                        recent_signals.append(sig)

            recent_signals = recent_signals[-max_signals:]

        except Exception:
            try:
                recent_signals = list(getattr(result, "signals", []) or [])[-max_signals:]
            except Exception:
                recent_signals = []

        return recent_bars, self._clone_result_with_updates(
            result,
            lines=light_lines,
            signals=recent_signals,
        )

    def _add_recent_backgrounds_to_figure(
            self,
            *,
            fig,
            engine,
            chart_bars,
            strategy_result,
            max_backgrounds: int = 2,
    ):
        """
        Lightweight playback background renderer.

        During replay playback, do not draw every historical background vrect.
        Draw only the background ranges overlapping the current visible chart window.
        """
        if chart_bars is None or chart_bars.empty or strategy_result is None:
            return fig

        backgrounds = list(getattr(strategy_result, "backgrounds", []) or [])
        if not backgrounds:
            return fig

        if "time" not in chart_bars.columns:
            return fig

        try:
            chart_times = pd.to_datetime(
                chart_bars["time"],
                errors="coerce",
                format="mixed",
            ).dropna()

            if chart_times.empty:
                return fig

            visible_start = chart_times.iloc[0]
            visible_end = chart_times.iloc[-1]

        except Exception:
            return fig

        overlapping = []

        for bg in backgrounds:
            try:
                bg_start = pd.to_datetime(
                    getattr(bg, "start_time", None),
                    errors="coerce",
                    format="mixed",
                )
                bg_end = pd.to_datetime(
                    getattr(bg, "end_time", None),
                    errors="coerce",
                    format="mixed",
                )

                if pd.isna(bg_start) or pd.isna(bg_end):
                    continue

                if bg_end >= visible_start and bg_start <= visible_end:
                    overlapping.append((bg, bg_start, bg_end))

            except Exception:
                continue

        if not overlapping:
            return fig

        for bg, bg_start, bg_end in overlapping[-max_backgrounds:]:
            try:
                x0 = max(bg_start, visible_start)
                x1 = min(bg_end, visible_end)

                if x1 <= x0:
                    continue

                color = engine._background_fill_color(bg.color)

                fig.add_vrect(
                    x0=x0,
                    x1=x1,
                    fillcolor=color,
                    opacity=1.0,
                    line_width=0,
                    layer="below",
                    annotation_text=None,
                )

            except Exception:
                continue

        return fig

    def add_to_figure(
            self,
            *,
            fig: go.Figure,
            engine,
            chart_bars: pd.DataFrame,
            strategy_result,
            is_replay_playing: bool,
            context: str = "WATCH",
    ) -> go.Figure:
        """
        Add strategy visuals to a Plotly figure.

        Active replay playback receives a lightweight recent overlay. Paused
        replay receives the full analysis overlay, including backgrounds.
        """
        if fig is None or engine is None or strategy_result is None:
            return fig

        overlay_start = time.perf_counter()

        overlay_bars = chart_bars
        overlay_result = strategy_result

        if is_replay_playing:
            overlay_bars, overlay_result = self.make_lightweight_replay_overlay(
                strategy_result,
                chart_bars,
                max_bars=self.replay_max_bars,
                max_signals=self.replay_max_signals,
            )

        if is_replay_playing:
            fig = self._add_recent_backgrounds_to_figure(
                fig=fig,
                engine=engine,
                chart_bars=overlay_bars,
                strategy_result=overlay_result,
                max_backgrounds=2,
            )
        else:
            fig = engine.add_backgrounds_to_figure(
                fig,
                chart_bars,
                strategy_result,
            )

        fig = engine.add_plots_to_figure(
            fig,
            overlay_bars,
            overlay_result,
        )

        fig = engine.add_signals_to_figure(
            fig,
            overlay_result,
        )

        overlay_ms = (time.perf_counter() - overlay_start) * 1000

        if overlay_ms > self.slow_log_ms:
            print(
                f"[{context} STRATEGY OVERLAY SLOW] {overlay_ms:.1f} ms "
                f"playing={is_replay_playing} "
                f"bars={len(overlay_bars) if overlay_bars is not None else 0} "
                f"signals={len(getattr(overlay_result, 'signals', []) or [])}",
                flush=True,
            )

        return fig
