from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import plotly.graph_objects as go


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
    Safe, small Pine-inspired strategy script engine.

    Strategy Language v0.2 foundation supports:

        fast = ema(close, 9)
        slow = ta.ema(close, 21)

        bullCross = crossover(fast, slow)
        bearCross = ta.crossunder(fast, slow)

        r = ta.rsi(close, 14)

        plot fast
        plot slow
        plot r

        buy when bullCross
        sell when ta.crossunder(fast, slow)

        buy when ta.crossunder(r, 30)
        sell when ta.crossover(r, 70)

    Safety:
        No eval.
        No exec.
        No imports.
        No raw Python execution.
        Only strict regex-parsed commands are supported.
    """

    NAME_PATTERN = r"[A-Za-z_][A-Za-z0-9_]*"
    FUNC_PATTERN = r"[A-Za-z_][A-Za-z0-9_\.]*"
    NUMBER_PATTERN = r"-?(?:\d+(?:\.\d*)?|\.\d+)"
    ARG_PATTERN = rf"(?:{NAME_PATTERN}|{NUMBER_PATTERN})"

    ASSIGN_RE = re.compile(
        rf"^(?P<name>{NAME_PATTERN})\s*=\s*"
        rf"(?P<func>{FUNC_PATTERN})\("
        rf"(?P<source>{NAME_PATTERN})\s*,\s*"
        r"(?P<length>\d+)\s*\)\s*$",
        flags=re.IGNORECASE,
    )

    BOOL_ASSIGN_RE = re.compile(
        rf"^(?P<name>{NAME_PATTERN})\s*=\s*"
        rf"(?P<func>crossover|crossunder|ta\.crossover|ta\.crossunder)\("
        rf"(?P<left>{ARG_PATTERN})\s*,\s*"
        rf"(?P<right>{ARG_PATTERN})\s*\)\s*$",
        flags=re.IGNORECASE,
    )

    PLOT_RE = re.compile(
        rf"^plot\s+(?P<name>{NAME_PATTERN})\s*$",
        flags=re.IGNORECASE,
    )

    SIGNAL_RE = re.compile(
        r"^(?P<side>buy|sell)\s+when\s+(?P<expr>.+?)\s*$",
        flags=re.IGNORECASE,
    )

    DIRECT_CROSS_RE = re.compile(
        rf"^(?P<func>crossover|crossunder|ta\.crossover|ta\.crossunder)\("
        rf"(?P<left>{ARG_PATTERN})\s*,\s*"
        rf"(?P<right>{ARG_PATTERN})\s*\)\s*$",
        flags=re.IGNORECASE,
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
        "__builtins__",
        "__import__",
    }

    FUNCTION_ALIASES = {
        "ta.sma": "sma",
        "ta.ema": "ema",
        "ta.rsi": "rsi",
        "ta.highest": "highest",
        "ta.lowest": "lowest",
        "ta.crossover": "crossover",
        "ta.crossunder": "crossunder",
    }

    SUPPORTED_INDICATORS = {"sma", "ema", "rsi", "highest", "lowest"}

    def run(self, script: str, bars: pd.DataFrame) -> StrategyScriptResult:
        result = StrategyScriptResult()

        if bars is None or bars.empty:
            result.errors.append("No bars available.")
            return result

        clean_bars = self._clean_bars(bars)

        if clean_bars.empty:
            result.errors.append("No valid bars available.")
            return result

        series_context = self._build_series_context(clean_bars)
        conditions: dict[str, pd.Series] = {}

        for raw_line in str(script or "").splitlines():
            line = raw_line.strip()

            if not line or line.startswith("#") or line.startswith("//"):
                continue

            line = self._strip_inline_comment(line).strip()
            if not line:
                continue

            unsafe = self._find_blocked_token(line)
            if unsafe:
                result.errors.append(f"Blocked unsafe token '{unsafe}' in line: {line}")
                continue

            bool_match = self.BOOL_ASSIGN_RE.match(line)
            if bool_match:
                self._handle_boolean_assignment(
                    bool_match,
                    clean_bars,
                    series_context,
                    conditions,
                    result,
                    line,
                )
                continue

            assign_match = self.ASSIGN_RE.match(line)
            if assign_match:
                self._handle_assignment(
                    assign_match,
                    clean_bars,
                    series_context,
                    result,
                    line,
                )
                continue

            plot_match = self.PLOT_RE.match(line)
            if plot_match:
                self._handle_plot(plot_match, result)
                continue

            signal_match = self.SIGNAL_RE.match(line)
            if signal_match:
                self._handle_signal(
                    signal_match,
                    clean_bars,
                    series_context,
                    conditions,
                    result,
                    line,
                )
                continue

            result.errors.append(f"Could not parse line: {line}")

        return result

    def add_plots_to_figure(
        self,
        fig: go.Figure,
        bars: pd.DataFrame,
        result: StrategyScriptResult,
    ) -> go.Figure:
        if bars is None or bars.empty or result is None:
            return fig

        clean_bars = self._clean_bars(bars)

        if clean_bars.empty:
            return fig

        x_values = clean_bars["time"] if "time" in clean_bars.columns else clean_bars.index

        for name in result.plots:
            series = result.lines.get(name)

            if series is None:
                continue

            try:
                y_values = series.reindex(clean_bars.index)
            except Exception:
                y_values = series

            fig.add_trace(
                go.Scatter(
                    x=x_values,
                    y=y_values,
                    mode="lines",
                    name=name,
                    line={"width": 1.6},
                    hovertemplate=f"{name}: %{{y:.4f}}<extra></extra>",
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

        buys = [sig for sig in result.signals if str(sig.side).upper() == "BUY"]
        sells = [sig for sig in result.signals if str(sig.side).upper() == "SELL"]

        if buys:
            fig.add_trace(
                go.Scatter(
                    x=[sig.time if sig.time is not None else sig.index for sig in buys],
                    y=[sig.price for sig in buys],
                    mode="markers+text",
                    name="Strategy BUY",
                    text=["BUY"] * len(buys),
                    textposition="bottom center",
                    marker={
                        "symbol": "triangle-up",
                        "size": 12,
                    },
                    hovertemplate=(
                        "BUY<br>"
                        "Time: %{x}<br>"
                        "Price: %{y:.4f}"
                        "<extra></extra>"
                    ),
                )
            )

        if sells:
            fig.add_trace(
                go.Scatter(
                    x=[sig.time if sig.time is not None else sig.index for sig in sells],
                    y=[sig.price for sig in sells],
                    mode="markers+text",
                    name="Strategy SELL",
                    text=["SELL"] * len(sells),
                    textposition="top center",
                    marker={
                        "symbol": "triangle-down",
                        "size": 12,
                    },
                    hovertemplate=(
                        "SELL<br>"
                        "Time: %{x}<br>"
                        "Price: %{y:.4f}"
                        "<extra></extra>"
                    ),
                )
            )

        return fig

    def _build_series_context(self, bars: pd.DataFrame) -> dict[str, pd.Series]:
        context: dict[str, pd.Series] = {}

        for col in ["open", "high", "low", "close", "volume"]:
            if col in bars.columns:
                context[col] = pd.to_numeric(bars[col], errors="coerce")

        return context

    def _clean_bars(self, bars: pd.DataFrame) -> pd.DataFrame:
        required = ["open", "high", "low", "close", "volume"]

        if bars is None or bars.empty:
            return pd.DataFrame(columns=["time", *required])

        df = bars.copy()

        if "time" in df.columns:
            df["time"] = pd.to_datetime(
                df["time"],
                errors="coerce",
                format="mixed",
            )

        for col in required:
            if col not in df.columns:
                df[col] = 0 if col == "volume" else pd.NA

            df[col] = pd.to_numeric(df[col], errors="coerce")

        subset = ["open", "high", "low", "close"]
        if "time" in df.columns:
            subset = ["time", *subset]

        df = df.dropna(subset=subset).copy()

        if "time" in df.columns:
            df = df.sort_values("time").copy()

        df = df.reset_index(drop=True)

        return df

    def _strip_inline_comment(self, line: str) -> str:
        out = str(line or "")

        hash_index = out.find("#")
        slash_index = out.find("//")

        indexes = [idx for idx in [hash_index, slash_index] if idx >= 0]
        if not indexes:
            return out

        return out[: min(indexes)]

    def _normalize_function_name(self, name: str) -> str:
        name = str(name or "").strip().lower()
        return self.FUNCTION_ALIASES.get(name, name)

    def _handle_assignment(
        self,
        match: re.Match,
        bars: pd.DataFrame,
        series_context: dict[str, pd.Series],
        result: StrategyScriptResult,
        line: str,
    ) -> None:
        name = match.group("name").strip()
        func_name = self._normalize_function_name(match.group("func"))
        source_name = match.group("source").strip()
        length = int(match.group("length"))

        if func_name not in self.SUPPORTED_INDICATORS:
            result.errors.append(f"Unsupported function '{func_name}' in line: {line}")
            return

        source = series_context.get(source_name)

        if source is None:
            result.errors.append(f"Unknown source '{source_name}' in line: {line}")
            return

        try:
            output = self._calculate_indicator(
                func_name=func_name,
                source=source,
                length=length,
            )
            output = pd.Series(output, index=bars.index, name=name)
        except Exception as exc:
            result.errors.append(f"Error calculating '{name}': {exc}")
            return

        result.lines[name] = output
        series_context[name] = output

    def _calculate_indicator(
        self,
        func_name: str,
        source: pd.Series,
        length: int,
    ) -> pd.Series:
        source = pd.to_numeric(pd.Series(source), errors="coerce")
        length = max(1, int(length))

        if func_name == "sma":
            return source.rolling(length, min_periods=length).mean()

        if func_name == "ema":
            return source.ewm(span=length, adjust=False, min_periods=length).mean()

        if func_name == "rsi":
            delta = source.diff()
            gains = delta.clip(lower=0)
            losses = -delta.clip(upper=0)

            avg_gain = gains.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
            avg_loss = losses.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()

            rs = avg_gain / avg_loss.replace(0, pd.NA)
            rsi = 100 - (100 / (1 + rs))

            # If avg_loss is zero and avg_gain is positive, RSI is 100.
            rsi = rsi.where(~((avg_loss == 0) & (avg_gain > 0)), 100)

            # If both are zero, price is flat. Use neutral RSI.
            rsi = rsi.where(~((avg_loss == 0) & (avg_gain == 0)), 50)

            return rsi

        if func_name == "highest":
            return source.rolling(length, min_periods=length).max()

        if func_name == "lowest":
            return source.rolling(length, min_periods=length).min()

        raise ValueError(f"Unsupported indicator: {func_name}")

    def _handle_boolean_assignment(
        self,
        match: re.Match,
        bars: pd.DataFrame,
        series_context: dict[str, pd.Series],
        conditions: dict[str, pd.Series],
        result: StrategyScriptResult,
        line: str,
    ) -> None:
        name = match.group("name").strip()
        func_name = self._normalize_function_name(match.group("func"))
        left_name = match.group("left").strip()
        right_name = match.group("right").strip()

        condition = self._make_cross_condition(
            func_name=func_name,
            left_name=left_name,
            right_name=right_name,
            bars=bars,
            series_context=series_context,
        )

        if condition is None:
            result.errors.append(f"Could not parse boolean assignment: {line}")
            return

        conditions[name] = condition.fillna(False).astype(bool)

    def _handle_plot(self, match: re.Match, result: StrategyScriptResult) -> None:
        name = match.group("name").strip()

        if name not in result.lines:
            result.errors.append(f"Cannot plot unknown line: {name}")
            return

        if name not in result.plots:
            result.plots.append(name)

    def _handle_signal(
        self,
        match: re.Match,
        bars: pd.DataFrame,
        series_context: dict[str, pd.Series],
        conditions: dict[str, pd.Series],
        result: StrategyScriptResult,
        line: str,
    ) -> None:
        side = match.group("side").upper().strip()
        expr = match.group("expr").strip()

        condition = self._resolve_signal_condition(
            expr=expr,
            bars=bars,
            series_context=series_context,
            conditions=conditions,
        )

        if condition is None:
            result.errors.append(f"Could not parse signal condition: {line}")
            return

        condition = condition.fillna(False).astype(bool)

        for idx, is_signal in condition.items():
            if not bool(is_signal):
                continue

            try:
                price = float(bars.loc[idx, "close"])
            except Exception:
                continue

            signal_time = bars.loc[idx, "time"] if "time" in bars.columns else idx

            result.signals.append(
                StrategySignal(
                    index=int(idx),
                    time=signal_time,
                    side=side,
                    price=price,
                    rule=line,
                )
            )

    def _resolve_signal_condition(
        self,
        expr: str,
        bars: pd.DataFrame,
        series_context: dict[str, pd.Series],
        conditions: dict[str, pd.Series],
    ) -> pd.Series | None:
        expr = str(expr or "").strip()

        if expr in conditions:
            return conditions[expr]

        direct_match = self.DIRECT_CROSS_RE.match(expr)
        if direct_match:
            func_name = self._normalize_function_name(direct_match.group("func"))
            left_name = direct_match.group("left").strip()
            right_name = direct_match.group("right").strip()

            return self._make_cross_condition(
                func_name=func_name,
                left_name=left_name,
                right_name=right_name,
                bars=bars,
                series_context=series_context,
            )

        return None

    def _resolve_series_or_number(
        self,
        value: str,
        bars: pd.DataFrame,
        series_context: dict[str, pd.Series],
    ) -> pd.Series | None:
        """
        Resolve a crossover/crossunder argument.

        Supports:
            fast
            slow
            r
            close
            open
            high
            low
            volume
            30
            70
            3.5
            -10
        """

        value = str(value or "").strip()

        if value in series_context:
            return pd.to_numeric(pd.Series(series_context[value]), errors="coerce")

        if value in bars.columns:
            return pd.to_numeric(pd.Series(bars[value]), errors="coerce")

        try:
            number = float(value)
            return pd.Series(number, index=bars.index)
        except Exception:
            return None

    def _make_cross_condition(
        self,
        func_name: str,
        left_name: str,
        right_name: str,
        bars: pd.DataFrame,
        series_context: dict[str, pd.Series],
    ) -> pd.Series | None:
        func_name = self._normalize_function_name(func_name)

        left = self._resolve_series_or_number(
            left_name,
            bars,
            series_context,
        )

        right = self._resolve_series_or_number(
            right_name,
            bars,
            series_context,
        )

        if left is None or right is None:
            return None

        left = pd.to_numeric(pd.Series(left), errors="coerce")
        right = pd.to_numeric(pd.Series(right), errors="coerce")

        if func_name == "crossover":
            return (left.shift(1) <= right.shift(1)) & (left > right)

        if func_name == "crossunder":
            return (left.shift(1) >= right.shift(1)) & (left < right)

        return None

    def _find_blocked_token(self, line: str) -> str | None:
        lowered = str(line or "").lower()

        for word in sorted(self.BLOCKED_WORDS):
            pattern = rf"(?<![A-Za-z0-9_]){re.escape(word)}(?![A-Za-z0-9_])"
            if re.search(pattern, lowered):
                return word

        if "__" in lowered:
            return "__"

        return None
