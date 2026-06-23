from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
import json
import math
import re
from typing import Any, Iterable, Optional

import pandas as pd


_SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|access[_-]?token|secret|password|bearer)\s*[:=]\s*['\"]?[^'\"\s,}]+"),
    re.compile(r"(?i)authorization\s*[:=]\s*bearer\s+[A-Za-z0-9._\-]+"),
]


def redact_secrets(text: Any) -> str:
    """Return text with obvious secrets redacted before AI/export use."""
    value = "" if text is None else str(text)
    for pattern in _SECRET_PATTERNS:
        value = pattern.sub(lambda m: m.group(0).split("=", 1)[0].split(":", 1)[0] + "=[REDACTED]", value)
    return value


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        number = float(value)
        if not math.isfinite(number):
            return None
        return number
    except Exception:
        return None


def _safe_int(value: Any) -> Optional[int]:
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except Exception:
        return None


def _clean_mapping(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    out: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            out[str(key)] = redact_secrets(value) if isinstance(value, str) else value
        elif isinstance(value, dict):
            out[str(key)] = _clean_mapping(value)
        elif isinstance(value, list):
            out[str(key)] = [
                _clean_mapping(item) if isinstance(item, dict) else redact_secrets(item)
                for item in value[:50]
            ]
        else:
            out[str(key)] = redact_secrets(value)
    return out


@dataclass
class BarSummary:
    rows: int = 0
    first_time: str = ""
    last_time: str = ""
    last_open: Optional[float] = None
    last_high: Optional[float] = None
    last_low: Optional[float] = None
    last_close: Optional[float] = None
    last_volume: Optional[float] = None
    close_change: Optional[float] = None
    close_change_pct: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    avg_volume: Optional[float] = None

    @property
    def available(self) -> bool:
        return self.rows > 0


@dataclass
class BacktestRuntimeState:
    has_run: bool = False
    auto_run_requested: bool = False
    auto_run_performed: bool = False
    status: str = "not_run"
    summary: dict[str, Any] = field(default_factory=dict)
    messages: list[str] = field(default_factory=list)

    @property
    def available(self) -> bool:
        return self.has_run and bool(self.summary)


@dataclass
class StrategyRuntimeContext:
    """
    A sanitized snapshot of what the user is currently doing in Strategy Lab.

    This object is intentionally broker-safe:
      - no account data
      - no positions
      - no open orders
      - no API keys
      - compact bar summary instead of raw full OHLCV history by default
    """

    symbol: str = ""
    timeframe: str = ""
    start: str = ""
    end: str = ""
    strategy_text: str = ""
    strategy_chars: int = 0
    initial_cash: Optional[float] = None
    quantity: Optional[float] = None
    commission: Optional[float] = None
    slippage: Optional[float] = None
    bars: BarSummary = field(default_factory=BarSummary)
    backtest: BacktestRuntimeState = field(default_factory=BacktestRuntimeState)
    validation_messages: list[str] = field(default_factory=list)
    user_question: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, default=str)

    def to_markdown(self) -> str:
        lines: list[str] = []
        lines.append("# Strategy Runtime Context")
        lines.append("")
        lines.append(f"- Created: {self.created_at}")
        lines.append(f"- Symbol: {self.symbol or 'not selected'}")
        lines.append(f"- Timeframe: {self.timeframe or 'not selected'}")
        lines.append(f"- Range: {self.start or 'not set'} -> {self.end or 'not set'}")
        lines.append(f"- Initial cash: {self.initial_cash if self.initial_cash is not None else 'not set'}")
        lines.append(f"- Quantity: {self.quantity if self.quantity is not None else 'not set'}")
        lines.append("")
        lines.append("## Bars Summary")
        if self.bars.available:
            lines.append(f"- Rows summarized: {self.bars.rows}")
            lines.append(f"- First bar: {self.bars.first_time}")
            lines.append(f"- Last bar: {self.bars.last_time}")
            lines.append(f"- Last OHLCV: {self.bars.last_open}, {self.bars.last_high}, {self.bars.last_low}, {self.bars.last_close}, {self.bars.last_volume}")
            lines.append(f"- Close change: {self.bars.close_change}")
            lines.append(f"- Close change %: {self.bars.close_change_pct}")
            lines.append(f"- Period high/low: {self.bars.high} / {self.bars.low}")
            lines.append(f"- Average volume: {self.bars.avg_volume}")
        else:
            lines.append("- No bars available.")
        lines.append("")
        lines.append("## Backtest")
        lines.append(f"- Status: {self.backtest.status}")
        lines.append(f"- Has run: {self.backtest.has_run}")
        lines.append(f"- Auto-run requested: {self.backtest.auto_run_requested}")
        lines.append(f"- Auto-run performed: {self.backtest.auto_run_performed}")
        if self.backtest.summary:
            lines.append("")
            lines.append("### Summary")
            for key, value in self.backtest.summary.items():
                lines.append(f"- {key}: {value}")
        if self.backtest.messages:
            lines.append("")
            lines.append("### Messages")
            for message in self.backtest.messages:
                lines.append(f"- {redact_secrets(message)}")
        lines.append("")
        lines.append("## Validation Messages")
        if self.validation_messages:
            for message in self.validation_messages:
                lines.append(f"- {redact_secrets(message)}")
        else:
            lines.append("- none")
        lines.append("")
        lines.append("## Strategy Script")
        lines.append("```text")
        lines.append(redact_secrets(self.strategy_text).strip() or "# no strategy text")
        lines.append("```")
        if self.user_question:
            lines.append("")
            lines.append("## User Question")
            lines.append(redact_secrets(self.user_question))
        return "\n".join(lines).strip() + "\n"

    def to_ai_context(self, *, max_strategy_chars: int = 12000) -> str:
        """
        Build an AI-ready context block.

        Keep this compact. The AI does not need the full raw bar dataframe by default.
        """
        clone = self.to_dict()
        strategy_text = redact_secrets(clone.get("strategy_text", ""))
        if len(strategy_text) > max_strategy_chars:
            strategy_text = strategy_text[:max_strategy_chars] + "\n...[TRUNCATED]"
        clone["strategy_text"] = strategy_text
        return (
            "You are receiving a user-approved strategy runtime context. "
            "Use it for advisory analysis only. Do not place trades, claim certainty, "
            "or request broker/account access.\n\n"
            + StrategyRuntimeContext.from_dict(clone).to_markdown()
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StrategyRuntimeContext":
        bars_data = data.get("bars") if isinstance(data, dict) else {}
        backtest_data = data.get("backtest") if isinstance(data, dict) else {}
        return cls(
            symbol=str(data.get("symbol", "") or ""),
            timeframe=str(data.get("timeframe", "") or ""),
            start=str(data.get("start", "") or ""),
            end=str(data.get("end", "") or ""),
            strategy_text=redact_secrets(data.get("strategy_text", "")),
            strategy_chars=_safe_int(data.get("strategy_chars")) or len(str(data.get("strategy_text", "") or "")),
            initial_cash=_safe_float(data.get("initial_cash")),
            quantity=_safe_float(data.get("quantity")),
            commission=_safe_float(data.get("commission")),
            slippage=_safe_float(data.get("slippage")),
            bars=BarSummary(**_filter_dataclass_kwargs(BarSummary, bars_data)),
            backtest=BacktestRuntimeState(**_filter_dataclass_kwargs(BacktestRuntimeState, backtest_data)),
            validation_messages=[redact_secrets(x) for x in data.get("validation_messages", []) if x is not None][:100],
            user_question=redact_secrets(data.get("user_question", "")),
            metadata=_clean_mapping(data.get("metadata", {})),
            created_at=str(data.get("created_at") or datetime.now().isoformat(timespec="seconds")),
        )


def _filter_dataclass_kwargs(cls: Any, data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    allowed = set(getattr(cls, "__dataclass_fields__", {}).keys())
    return {key: value for key, value in data.items() if key in allowed}


def summarize_bars(
    bars: Any,
    *,
    max_rows: int = 500,
    time_col_candidates: Iterable[str] = ("time", "datetime", "date", "timestamp"),
) -> BarSummary:
    """
    Summarize OHLCV bars for AI context.

    Accepts pandas DataFrame, records list, or any object convertible to DataFrame.
    It intentionally returns a compact summary instead of raw bars.
    """
    try:
        df = bars if isinstance(bars, pd.DataFrame) else pd.DataFrame(bars)
    except Exception:
        return BarSummary()

    if df is None or df.empty:
        return BarSummary()

    df = df.copy()
    if max_rows and len(df) > max_rows:
        df = df.tail(max_rows).copy()

    lower_map = {str(col).lower(): col for col in df.columns}

    def col(*names: str) -> Optional[str]:
        for name in names:
            if name in df.columns:
                return name
            if name.lower() in lower_map:
                return lower_map[name.lower()]
        return None

    time_col = None
    for candidate in time_col_candidates:
        time_col = col(candidate)
        if time_col:
            break

    open_col = col("open", "o")
    high_col = col("high", "h")
    low_col = col("low", "l")
    close_col = col("close", "c")
    volume_col = col("volume", "v")

    if close_col:
        df[close_col] = pd.to_numeric(df[close_col], errors="coerce")
    if high_col:
        df[high_col] = pd.to_numeric(df[high_col], errors="coerce")
    if low_col:
        df[low_col] = pd.to_numeric(df[low_col], errors="coerce")
    if volume_col:
        df[volume_col] = pd.to_numeric(df[volume_col], errors="coerce")

    last = df.iloc[-1]
    first = df.iloc[0]

    first_close = _safe_float(first.get(close_col)) if close_col else None
    last_close = _safe_float(last.get(close_col)) if close_col else None
    close_change = None
    close_change_pct = None

    if first_close is not None and last_close is not None:
        close_change = last_close - first_close
        if first_close != 0:
            close_change_pct = (close_change / first_close) * 100.0

    return BarSummary(
        rows=int(len(df)),
        first_time=str(first.get(time_col, "")) if time_col else "",
        last_time=str(last.get(time_col, "")) if time_col else "",
        last_open=_safe_float(last.get(open_col)) if open_col else None,
        last_high=_safe_float(last.get(high_col)) if high_col else None,
        last_low=_safe_float(last.get(low_col)) if low_col else None,
        last_close=last_close,
        last_volume=_safe_float(last.get(volume_col)) if volume_col else None,
        close_change=close_change,
        close_change_pct=close_change_pct,
        high=_safe_float(df[high_col].max()) if high_col else None,
        low=_safe_float(df[low_col].min()) if low_col else None,
        avg_volume=_safe_float(df[volume_col].mean()) if volume_col else None,
    )


def build_strategy_runtime_context(
    *,
    strategy_text: str = "",
    symbol: str = "",
    timeframe: str = "",
    start: str = "",
    end: str = "",
    initial_cash: Any = None,
    quantity: Any = None,
    commission: Any = None,
    slippage: Any = None,
    bars: Any = None,
    backtest_summary: Optional[dict[str, Any]] = None,
    backtest_has_run: bool = False,
    backtest_status: str = "not_run",
    backtest_messages: Optional[list[str]] = None,
    validation_messages: Optional[list[str]] = None,
    user_question: str = "",
    auto_run_requested: bool = False,
    auto_run_performed: bool = False,
    metadata: Optional[dict[str, Any]] = None,
) -> StrategyRuntimeContext:
    clean_strategy = redact_secrets(strategy_text)
    return StrategyRuntimeContext(
        symbol=str(symbol or "").upper().strip(),
        timeframe=str(timeframe or "").strip(),
        start=str(start or "").strip(),
        end=str(end or "").strip(),
        strategy_text=clean_strategy,
        strategy_chars=len(clean_strategy),
        initial_cash=_safe_float(initial_cash),
        quantity=_safe_float(quantity),
        commission=_safe_float(commission),
        slippage=_safe_float(slippage),
        bars=summarize_bars(bars),
        backtest=BacktestRuntimeState(
            has_run=bool(backtest_has_run),
            auto_run_requested=bool(auto_run_requested),
            auto_run_performed=bool(auto_run_performed),
            status=str(backtest_status or ("completed" if backtest_has_run else "not_run")),
            summary=_clean_mapping(backtest_summary or {}),
            messages=[redact_secrets(x) for x in (backtest_messages or []) if x is not None][:100],
        ),
        validation_messages=[redact_secrets(x) for x in (validation_messages or []) if x is not None][:100],
        user_question=redact_secrets(user_question),
        metadata=_clean_mapping(metadata or {}),
    )


def should_auto_run_backtest_for_ai(
    *,
    has_backtest_run: bool,
    user_requested_ai: bool,
    allow_auto_run: bool,
) -> bool:
    """
    Decide if the app may run a local backtest before asking AI.

    This must stay local and broker-free. The UI should show this behavior clearly.
    """
    return bool(user_requested_ai and allow_auto_run and not has_backtest_run)
