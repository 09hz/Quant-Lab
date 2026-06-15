from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd
import plotly.graph_objects as go

from core.IndicatorEngine import IndicatorEngine


@dataclass
class StrategyScriptResult:
    lines: dict[str, pd.Series] = field(default_factory=dict)
    plots: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class StrategyEngine:
    """
    Tiny PineScript-like strategy script engine.

    Phase 1 supports indicator plotting only:

        fast = sma(close, 9)
        slow = sma(close, 21)
        plot fast
        plot slow

    No eval.
    No exec.
    No imports.
    No raw Python execution.
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

        clean_bars = bars.copy()

        if "time" in clean_bars.columns:
            clean_bars["time"] = pd.to_datetime(
                clean_bars["time"],
                errors="coerce",
                format="mixed",
            )

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
                name = plot_match.group("name")

                if name not in result.lines:
                    result.errors.append(f"Cannot plot unknown line: {name}")
                    continue

                result.plots.append(name)
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

        if "time" in bars.columns:
            x_values = pd.to_datetime(
                bars["time"],
                errors="coerce",
                format="mixed",
            )
        else:
            x_values = bars.index

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

    def _find_blocked_token(self, line: str) -> str | None:
        lowered = line.lower()

        # Always block dunder access anywhere.
        if "__" in lowered:
            return "__"

        # Block only complete dangerous words, not substrings inside safe words.
        # Example:
        #   "os" should be blocked
        #   "close" should NOT be blocked
        for token in self.BLOCKED_WORDS:
            pattern = rf"\b{re.escape(token)}\b"
            if re.search(pattern, lowered):
                return token

        return None