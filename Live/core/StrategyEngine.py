from __future__ import annotations

import ast
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
    Safe Pine-inspired Strategy Lab engine.

    Supported examples:

        fast = ta.ema(close, 9)
        slow = ta.ema(close, 21)
        trend = ta.ema(close, 50)
        r = ta.rsi(close, 14)

        bullCross = ta.crossover(fast, slow)
        bearCross = ta.crossunder(fast, slow)

        aboveTrend = close > trend
        notOverbought = r < 70

        longSignal = bullCross and aboveTrend and notOverbought
        exitSignal = bearCross or r > 80

        plot fast
        plot slow
        plot trend

        buy when longSignal
        sell when exitSignal

    Safety:
        No eval.
        No exec.
        No imports.
        No raw Python execution.
        Expressions are parsed with Python AST and only a small whitelist
        of nodes/functions is evaluated.
    """

    NAME_PATTERN = r"[A-Za-z_][A-Za-z0-9_]*"
    FUNC_PATTERN = r"[A-Za-z_][A-Za-z0-9_\.]*"

    ASSIGN_RE = re.compile(
        rf"^(?P<name>{NAME_PATTERN})\s*=\s*"
        rf"(?P<func>{FUNC_PATTERN})\("
        rf"(?P<source>{NAME_PATTERN})\s*,\s*"
        r"(?P<length>\d+)\s*\)\s*$",
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
    SUPPORTED_CONDITION_FUNCTIONS = {"crossover", "crossunder"}

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
            original_raw_line = str(raw_line or "")
            line = original_raw_line.strip()

            if not line or line.startswith("#") or line.startswith("//"):
                continue

            line = self._strip_inline_comment(line).strip()
            if not line:
                continue

            line = self._normalize_strategy_aliases(line)

            unsafe = self._find_blocked_token(line)
            if unsafe:
                result.errors.append(f"Blocked unsafe token '{unsafe}' in line: {line}")
                continue

            # 1. Indicator assignment:
            #    fast = ta.ema(close, 9)
            assign_match = self.ASSIGN_RE.match(line)
            if assign_match:
                self._handle_indicator_assignment(
                    assign_match,
                    clean_bars,
                    series_context,
                    result,
                    line,
                )
                continue

            # 2. General boolean/expression assignment:
            #    bullCross = crossover(fast, slow)
            #    aboveTrend = close > trend
            #    longSignal = bullCross and aboveTrend
            generic_assignment = self._parse_generic_assignment(line)
            if generic_assignment is not None:
                name, expr = generic_assignment

                condition = self._evaluate_condition_expression(
                    expr=expr,
                    bars=clean_bars,
                    series_context=series_context,
                    conditions=conditions,
                )
                condition = self._to_bool_series(condition, clean_bars)

                if condition is None:
                    result.errors.append(f"Could not parse assignment: {line}")
                    continue

                conditions[name] = condition
                continue

            # 3. Plot command:
            #    plot fast
            plot_match = self.PLOT_RE.match(line)
            if plot_match:
                self._handle_plot(plot_match, result)
                continue

            # 4. Signal command:
            #    buy when longSignal
            #    sell when bearCross or r > 80
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

    def _normalize_strategy_aliases(self, line: str) -> str:
        """
        Convert Pine-style ta.* aliases into current internal function names.

        This is intentionally simple and keeps the AST evaluator from seeing
        unsupported attribute calls like ta.ema(...).
        """

        out = str(line or "")

        replacements = {
            "ta.sma(": "sma(",
            "ta.ema(": "ema(",
            "ta.rsi(": "rsi(",
            "ta.highest(": "highest(",
            "ta.lowest(": "lowest(",
            "ta.crossover(": "crossover(",
            "ta.crossunder(": "crossunder(",
        }

        for old, new in replacements.items():
            out = out.replace(old, new)

        return out

    def _parse_generic_assignment(self, line: str) -> tuple[str, str] | None:
        match = re.match(
            rf"^(?P<name>{self.NAME_PATTERN})\s*=\s*(?P<expr>.+?)\s*$",
            line,
            flags=re.IGNORECASE,
        )

        if not match:
            return None

        name = match.group("name").strip()
        expr = match.group("expr").strip()

        if not name or not expr:
            return None

        return name, expr

    def _handle_indicator_assignment(
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

        condition = self._evaluate_condition_expression(
            expr=expr,
            bars=bars,
            series_context=series_context,
            conditions=conditions,
        )
        condition = self._to_bool_series(condition, bars)

        if condition is None:
            result.errors.append(f"Could not parse signal condition: {line}")
            return

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

    def _resolve_expression_value(
        self,
        name: str,
        bars: pd.DataFrame,
        series_context: dict[str, pd.Series],
        conditions: dict[str, pd.Series],
    ):
        """
        Resolve names used in strategy expressions.

        Supports:
            close
            open
            high
            low
            volume
            plotted indicator names
            boolean condition names
            numeric constants
        """

        name = str(name or "").strip()

        if name in conditions:
            return conditions[name]

        if name in series_context:
            return series_context[name]

        if name in bars.columns:
            return bars[name]

        try:
            number = float(name)
            return pd.Series(number, index=bars.index)
        except Exception:
            return None

    def _to_bool_series(self, value, bars: pd.DataFrame) -> pd.Series | None:
        """
        Convert expression output into a boolean Series.
        """

        if isinstance(value, pd.Series):
            # Boolean series should stay boolean.
            if str(value.dtype) == "bool":
                return value.fillna(False).astype(bool)

            # Numeric series as a condition means non-zero and non-null.
            numeric = pd.to_numeric(value, errors="coerce")
            return numeric.fillna(0).ne(0)

        if isinstance(value, bool):
            return pd.Series(value, index=bars.index)

        if value is None:
            return None

        try:
            return pd.Series(bool(value), index=bars.index)
        except Exception:
            return None

    def _eval_ast_expression(
        self,
        node,
        bars: pd.DataFrame,
        series_context: dict[str, pd.Series],
        conditions: dict[str, pd.Series],
    ):
        """
        Safely evaluate a small expression language.

        Supported:
            names
            numbers
            comparisons
            and/or/not
            crossover(...)
            crossunder(...)

        Explicitly unsupported:
            attributes
            subscripts
            comprehensions
            lambdas
            imports
            function calls except crossover/crossunder
        """

        if isinstance(node, ast.Expression):
            return self._eval_ast_expression(
                node.body,
                bars,
                series_context,
                conditions,
            )

        if isinstance(node, ast.Name):
            return self._resolve_expression_value(
                node.id,
                bars,
                series_context,
                conditions,
            )

        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float, bool)):
                return pd.Series(node.value, index=bars.index)
            return None

        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            value = self._eval_ast_expression(
                node.operand,
                bars,
                series_context,
                conditions,
            )
            value = self._to_bool_series(value, bars)

            if value is None:
                return None

            return ~value

        if isinstance(node, ast.BoolOp):
            values = []

            for child in node.values:
                value = self._eval_ast_expression(
                    child,
                    bars,
                    series_context,
                    conditions,
                )
                value = self._to_bool_series(value, bars)

                if value is None:
                    return None

                values.append(value)

            if not values:
                return None

            result = values[0]

            for value in values[1:]:
                if isinstance(node.op, ast.And):
                    result = result & value
                elif isinstance(node.op, ast.Or):
                    result = result | value
                else:
                    return None

            return result

        if isinstance(node, ast.Compare):
            left = self._eval_ast_expression(
                node.left,
                bars,
                series_context,
                conditions,
            )

            if left is None:
                return None

            result = pd.Series(True, index=bars.index)
            current_left = left

            for op, comparator in zip(node.ops, node.comparators):
                right = self._eval_ast_expression(
                    comparator,
                    bars,
                    series_context,
                    conditions,
                )

                if right is None:
                    return None

                if isinstance(op, ast.Gt):
                    part = current_left > right
                elif isinstance(op, ast.Lt):
                    part = current_left < right
                elif isinstance(op, ast.GtE):
                    part = current_left >= right
                elif isinstance(op, ast.LtE):
                    part = current_left <= right
                elif isinstance(op, ast.Eq):
                    part = current_left == right
                elif isinstance(op, ast.NotEq):
                    part = current_left != right
                else:
                    return None

                if isinstance(part, pd.Series):
                    part = part.fillna(False)
                else:
                    part = pd.Series(bool(part), index=bars.index)

                result = result & part.astype(bool)
                current_left = right

            return result

        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                return None

            func_name = self._normalize_function_name(node.func.id)

            if func_name not in self.SUPPORTED_CONDITION_FUNCTIONS:
                return None

            if len(node.args) != 2:
                return None

            left = self._eval_ast_expression(
                node.args[0],
                bars,
                series_context,
                conditions,
            )
            right = self._eval_ast_expression(
                node.args[1],
                bars,
                series_context,
                conditions,
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

    def _evaluate_condition_expression(
        self,
        expr: str,
        bars: pd.DataFrame,
        series_context: dict[str, pd.Series],
        conditions: dict[str, pd.Series],
    ):
        expr = str(expr or "").strip()
        expr = self._normalize_strategy_aliases(expr)

        if not expr:
            return None

        try:
            tree = ast.parse(expr, mode="eval")
        except SyntaxError:
            return None

        return self._eval_ast_expression(
            tree,
            bars,
            series_context,
            conditions,
        )

    def _find_blocked_token(self, line: str) -> str | None:
        lowered = str(line or "").lower()

        for word in sorted(self.BLOCKED_WORDS):
            pattern = rf"(?<![A-Za-z0-9_]){re.escape(word)}(?![A-Za-z0-9_])"
            if re.search(pattern, lowered):
                return word

        if "__" in lowered:
            return "__"

        return None
