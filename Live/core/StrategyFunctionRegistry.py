from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


StrategyFunctionStatus = Literal["supported", "planned", "experimental"]


@dataclass(frozen=True)
class StrategyFunctionSpec:
    name: str
    category: str
    signature: str
    returns: str
    description: str
    example: str
    backend: str
    status: StrategyFunctionStatus = "supported"


FUNCTION_REGISTRY: dict[str, StrategyFunctionSpec] = {
    "sma": StrategyFunctionSpec(
        name="sma",
        category="Moving Average",
        signature="sma(source, length)",
        returns="series",
        description="Simple moving average.",
        example="fast = sma(close, 9)",
        backend="internal",
    ),
    "ema": StrategyFunctionSpec(
        name="ema",
        category="Moving Average",
        signature="ema(source, length)",
        returns="series",
        description="Exponential moving average.",
        example="trend = ema(close, 21)",
        backend="internal",
    ),
    "rsi": StrategyFunctionSpec(
        name="rsi",
        category="Momentum",
        signature="rsi(source, length)",
        returns="series",
        description="Relative Strength Index.",
        example="r = rsi(close, 14)",
        backend="internal",
    ),
    "highest": StrategyFunctionSpec(
        name="highest",
        category="Range",
        signature="highest(source, length)",
        returns="series",
        description="Rolling highest value.",
        example="resistance = highest(high, 20)",
        backend="internal",
    ),
    "lowest": StrategyFunctionSpec(
        name="lowest",
        category="Range",
        signature="lowest(source, length)",
        returns="series",
        description="Rolling lowest value.",
        example="support = lowest(low, 20)",
        backend="internal",
    ),
    "crossover": StrategyFunctionSpec(
        name="crossover",
        category="Signal",
        signature="crossover(a, b)",
        returns="boolean_series",
        description="True when series a crosses above series b.",
        example="buy when crossover(fast, slow)",
        backend="internal",
    ),
    "crossunder": StrategyFunctionSpec(
        name="crossunder",
        category="Signal",
        signature="crossunder(a, b)",
        returns="boolean_series",
        description="True when series a crosses below series b.",
        example="sell when crossunder(fast, slow)",
        backend="internal",
    ),

    # Planned Pine-like aliases.
    "ta.sma": StrategyFunctionSpec(
        name="ta.sma",
        category="Moving Average",
        signature="ta.sma(source, length)",
        returns="series",
        description="Pine-style alias for sma.",
        example="fast = ta.sma(close, 9)",
        backend="planned pandas-ta-classic/internal adapter",
        status="planned",
    ),
    "ta.ema": StrategyFunctionSpec(
        name="ta.ema",
        category="Moving Average",
        signature="ta.ema(source, length)",
        returns="series",
        description="Pine-style alias for ema.",
        example="fast = ta.ema(close, 9)",
        backend="planned pandas-ta-classic/internal adapter",
        status="planned",
    ),
    "ta.atr": StrategyFunctionSpec(
        name="ta.atr",
        category="Volatility",
        signature="ta.atr(length)",
        returns="series",
        description="Average True Range.",
        example="atrLine = ta.atr(14)",
        backend="planned pandas-ta-classic/internal adapter",
        status="planned",
    ),
    "ta.supertrend": StrategyFunctionSpec(
        name="ta.supertrend",
        category="Trend",
        signature="ta.supertrend(factor, atr_length)",
        returns="series, series",
        description="Supertrend line and trend direction.",
        example="supertrendLine, trendDirection = ta.supertrend(3.0, 10)",
        backend="planned pandas-ta-classic/custom adapter",
        status="planned",
    ),
}


def get_supported_function_names() -> list[str]:
    return [
        name
        for name, spec in FUNCTION_REGISTRY.items()
        if spec.status == "supported"
    ]


def get_planned_function_names() -> list[str]:
    return [
        name
        for name, spec in FUNCTION_REGISTRY.items()
        if spec.status == "planned"
    ]


def get_function_reference_markdown() -> str:
    lines = ["# Strategy Function Reference", ""]

    for name in sorted(FUNCTION_REGISTRY):
        spec = FUNCTION_REGISTRY[name]
        lines.extend(
            [
                f"## `{spec.signature}`",
                "",
                f"Status: `{spec.status}`",
                "",
                spec.description,
                "",
                f"Returns: `{spec.returns}`",
                "",
                "Example:",
                "",
                "```text",
                spec.example,
                "```",
                "",
            ]
        )

    return "\n".join(lines)