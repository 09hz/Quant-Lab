from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import plotly.graph_objects as go

from core.IndicatorEngine import IndicatorEngine


@dataclass
class StrategySignal:
    index: int
    time: Any
    side: str
    price: float
    rule: str


@dataclass
class StrategyScriptResult:
    lines: dict[str, pd.Series] = field(default_factory=dict)
    plots: list[str] = field(default_factory=list)
    signals: list[StrategySignal] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class StrategyEngine:
    """
    Tiny PineScript-like strategy script engine.

    Phase 1:
        fast = sma(close, 9)
        slow = ema(close, 21)
        plot fast
        plot slow

    Phase 2:
        buy when crossover(fast, slow)
        sell when crossunder(fast, slow)

    Safety:
        No eval.
        No exec.
        No imports.
        No raw Python execution.
        Only strict regex-parsed commands are supported.
    """

    ASSIGN_RE = re.compile(
        r"^(?P<name>[a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*"
        r"(?P<func>[a-zA-Z_][a-zA-Z0-9_]*)\("
        r"(?P<source>[a-zA-Z_][a-zA-Z0-9_]*)\s*,\s*"
        r"(?P<length>\d+)\)$"
    )

    PLOT_RE = re.compile(
        r"^plot\s+(?P<name>[a-zA-Z_][a-zA-Z0-9_]*)$"
    )

    SIGNAL_RE = re.compile(
        r"^(?P<side>buy|sell)\s+when\s+"
        r"(?P<func>crossover|crossunder)\("
        r"(?P<left>[a-zA-Z_][a-zA-Z0-9_]*)\s*,\s*"
        r"(?P<right>[a-zA-Z_][a-zA-Z0-9_]*)\)$"
    )

    BLOCKED_WORDS = {
        "import",
        "exec",
        "eval",
        "open",
        "os",
        "sys",
        "subprocess",
        "socket",
        "requests",
        "class",
        "def",
        "lambda",
        "while",
        "for",
        "with",
        "try",
        "except",
        "raise",
        "return",
        "globals",
        "locals",
        "compile",
        "input",
        "print",
        "setattr",
        "getattr",
        "delattr",
    }

    def __init__(self):
        self.indicators = IndicatorEngine()

        self.allowed_functions = {
            "sma": self.indicators.sma,
            "ema": self.indicators.ema,
            "rsi": self.indicators.rsi,
            "highest": self.indicators.highest,
            "lowest": self.indicators.lowest,
        }

    def run(self, script: str, bars: pd.DataFrame) -> StrategyScriptResult:
        result = StrategyScriptResult()

        if bars is None or bars.empty:
            result.errors.append("No bars available.")
            return result

        clean_bars = self._clean_bars(bars)

        if clean_bars.empty:
            result.errors.append("No valid bars available.")
            return result

        for raw_line in str(script or "").splitlines():
            line = raw_line.strip()

            if not line or line.startswith("#"):
                continue

            unsafe = self._find_blocked_token(line)
            if unsafe:
                result.errors.append(f"Blocked unsafe token '{unsafe}' in line: {line}")
                continue

            assign_match = self.ASSIGN_RE.match(line)
            if assign_match:
                self._handle_assignment(assign_match, clean_bars, result)
                continue

            plot_match = self.PLOT_RE.match(line)
            if plot_match:
                self._handle_plot(plot_match, result)
                continue

            signal_match = self.SIGNAL_RE.match(line.lower())
            if signal_match:
                self._handle_signal(signal_match, clean_bars, result, line)
                continue

            result.errors.append(f"Could not parse line: {line}")

        return result

    def add_plots_to_figure(
        self,
        fig: go.Figure,
        bars: pd.DataFrame,
        result: StrategyScriptResult,
    ) -> go.Figure:
        if bars is None or bars.empty:
            return fig

        clean_bars = self._clean_bars(bars)

        if clean_bars.empty:
            return fig

        if "time" in clean_bars.columns:
            x_values = clean_bars["time"]
        else:
            x_values = clean_bars.index

        for name in result.plots:
            series = result.lines.get(name)

            if series is None:
                continue

            fig.add_trace(
                go.Scatter(
                    x=x_values,
                    y=series,
                    mode="lines",
                    name=name,
                    line=dict(width=2),
                    hovertemplate=(
                        f"{name}<br>"
                        "Time: %{x}<br>"
                        "Value: %{y:,.4f}"
                        "<extra></extra>"
                    ),
                )
            )

        return fig

    def add_signals_to_figure(
        self,
        fig: go.Figure,
        result: StrategyScriptResult,
    ) -> go.Figure:
        if result is None or not result.signals:
            return fig

        buy_x = []
        buy_y = []
        buy_text = []

        sell_x = []
        sell_y = []
        sell_text = []

        for signal in result.signals:
            hover = (
                f"{signal.side}<br>"
                f"Time: {signal.time}<br>"
                f"Price: ${signal.price:,.2f}<br>"
                f"Rule: {signal.rule}"
            )

            if signal.side == "BUY":
                buy_x.append(signal.time)
                buy_y.append(signal.price)
                buy_text.append(hover)
            elif signal.side == "SELL":
                sell_x.append(signal.time)
                sell_y.append(signal.price)
                sell_text.append(hover)

        if buy_x:
            fig.add_trace(
                go.Scatter(
                    x=buy_x,
                    y=buy_y,
                    mode="markers",
                    name="Strategy BUY",
                    marker=dict(
                        symbol="triangle-up",
                        size=13,
                        color="#34d399",
                        line=dict(width=1, color="#ffffff"),
                    ),
                    text=buy_text,
                    hovertemplate="%{text}<extra></extra>",
                )
            )

        if sell_x:
            fig.add_trace(
                go.Scatter(
                    x=sell_x,
                    y=sell_y,
                    mode="markers",
                    name="Strategy SELL",
                    marker=dict(
                        symbol="triangle-down",
                        size=13,
                        color="#ff6b6b",
                        line=dict(width=1, color="#ffffff"),
                    ),
                    text=sell_text,
                    hovertemplate="%{text}<extra></extra>",
                )
            )

        return fig

    def _handle_assignment(
        self,
        match,
        bars: pd.DataFrame,
        result: StrategyScriptResult,
    ) -> None:
        name = match.group("name")
        func_name = match.group("func").lower()
        source = match.group("source").lower()
        length = int(match.group("length"))

        if func_name not in self.allowed_functions:
            result.errors.append(f"Unsupported function: {func_name}")
            return

        try:
            result.lines[name] = self.allowed_functions[func_name](
                bars,
                source,
                length,
            )
        except Exception as exc:
            result.errors.append(f"{name}: {exc}")

    def _handle_plot(self, match, result: StrategyScriptResult) -> None:
        name = match.group("name")

        if name not in result.lines:
            result.errors.append(f"Cannot plot unknown line: {name}")
            return

        result.plots.append(name)

    def _handle_signal(
        self,
        match,
        bars: pd.DataFrame,
        result: StrategyScriptResult,
        original_line: str,
    ) -> None:
        side = match.group("side").upper()
        func_name = match.group("func").lower()
        left_name = match.group("left")
        right_name = match.group("right")

        if left_name not in result.lines:
            result.errors.append(f"Signal references unknown line: {left_name}")
            return

        if right_name not in result.lines:
            result.errors.append(f"Signal references unknown line: {right_name}")
            return

        left = pd.to_numeric(result.lines[left_name], errors="coerce")
        right = pd.to_numeric(result.lines[right_name], errors="coerce")

        if func_name == "crossover":
            mask = self._crossover(left, right)
        elif func_name == "crossunder":
            mask = self._crossunder(left, right)
        else:
            result.errors.append(f"Unsupported signal function: {func_name}")
            return

        close = pd.to_numeric(bars["close"], errors="coerce")

        if "time" in bars.columns:
            times = bars["time"]
        else:
            times = bars.index

        for idx, triggered in mask.fillna(False).items():
            if not bool(triggered):
                continue

            if idx >= len(close):
                continue

            price = close.iloc[idx]

            if pd.isna(price):
                continue

            result.signals.append(
                StrategySignal(
                    index=int(idx),
                    time=times.iloc[idx] if hasattr(times, "iloc") else times[idx],
                    side=side,
                    price=float(price),
                    rule=original_line,
                )
            )

    def _crossover(self, left: pd.Series, right: pd.Series) -> pd.Series:
        return (left.shift(1) <= right.shift(1)) & (left > right)

    def _crossunder(self, left: pd.Series, right: pd.Series) -> pd.Series:
        return (left.shift(1) >= right.shift(1)) & (left < right)

    def _clean_bars(self, bars: pd.DataFrame) -> pd.DataFrame:
        clean_bars = bars.copy()

        required = ["open", "high", "low", "close"]
        for col in required:
            if col not in clean_bars.columns:
                raise ValueError(f"Bars are missing column: {col}")

            clean_bars[col] = pd.to_numeric(clean_bars[col], errors="coerce")

        if "time" in clean_bars.columns:
            clean_bars["time"] = pd.to_datetime(
                clean_bars["time"],
                errors="coerce",
                format="mixed",
            )
            clean_bars = clean_bars.dropna(
                subset=["time", "open", "high", "low", "close"]
            ).copy()
        else:
            clean_bars = clean_bars.dropna(
                subset=["open", "high", "low", "close"]
            ).copy()

        clean_bars = clean_bars.reset_index(drop=True)
        return clean_bars

    def _find_blocked_token(self, line: str) -> str | None:
        lowered = line.lower()

        if "__" in lowered:
            return "__"

        for token in self.BLOCKED_WORDS:
            pattern = rf"\b{re.escape(token)}\b"
            if re.search(pattern, lowered):
                return token

        return None