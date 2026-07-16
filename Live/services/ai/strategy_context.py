from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Optional


CONTEXT_SCHEMA_VERSION = "strategy-context-v1"

SECRET_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"(?i)(OPENAI_API_KEY\s*=\s*)([^\s]+)", r"\1[REDACTED]"),
    (r"(?i)(TRADIER_ACCESS_TOKEN\s*=\s*)([^\s]+)", r"\1[REDACTED]"),
    (r"(?i)(LLM_API_KEY\s*=\s*)([^\s]+)", r"\1[REDACTED]"),
    (r"(?i)(Authorization:\s*Bearer\s+)([A-Za-z0-9_\-\.]+)", r"\1[REDACTED]"),
    (r"sk-[A-Za-z0-9_\-]{12,}", "[REDACTED_OPENAI_KEY]"),
    (r"(?i)(password\s*[:=]\s*)([^\s,;]+)", r"\1[REDACTED]"),
    (r"(?i)(secret\s*[:=]\s*)([^\s,;]+)", r"\1[REDACTED]"),
    (r"(?i)(token\s*[:=]\s*)([^\s,;]+)", r"\1[REDACTED]"),
)


def utc_now_text() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def coerce_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def coerce_number(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except Exception:
        return default


def redact_sensitive_text(text: str) -> str:
    """Mask obvious API keys/tokens before context is exported or sent to an LLM."""
    safe = coerce_text(text)
    for pattern, replacement in SECRET_PATTERNS:
        safe = re.sub(pattern, replacement, safe)
    return safe


def truncate_text(text: str, max_chars: int, label: str = "text") -> str:
    safe = coerce_text(text)
    if max_chars <= 0:
        return ""
    if len(safe) <= max_chars:
        return safe
    omitted = len(safe) - max_chars
    return safe[:max_chars] + f"\n\n[TRUNCATED {omitted} chars from {label}]"


def compact_mapping(mapping: Mapping[str, Any] | None) -> dict[str, Any]:
    if not mapping:
        return {}
    out: dict[str, Any] = {}
    for key, value in mapping.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            out[str(key)] = value
        elif isinstance(value, (list, tuple)):
            out[str(key)] = [
                item if isinstance(item, (str, int, float, bool)) else str(item)
                for item in value[:100]
            ]
        elif isinstance(value, Mapping):
            out[str(key)] = compact_mapping(value)
        else:
            out[str(key)] = str(value)
    return out


@dataclass
class StrategyContext:
    """
    Sanitized snapshot of the Strategy Lab state.

    This object is designed for two safe uses:
      1. Exporting current strategy/backtest state as JSON or Markdown.
      2. Sending selected, sanitized context to the advisory AI service.

    It should never include API keys, broker account details, or raw order-routing data.
    """

    schema_version: str = CONTEXT_SCHEMA_VERSION
    created_at: str = field(default_factory=utc_now_text)
    source: str = "strategy_lab"

    symbol: str = ""
    timeframe: str = ""
    start: str = ""
    end: str = ""

    strategy_name: str = ""
    strategy_text: str = ""

    initial_cash: Optional[float] = None
    quantity: Optional[float] = None
    commission: Optional[float] = None
    slippage: Optional[float] = None

    backtest_summary: dict[str, Any] = field(default_factory=dict)
    validation_messages: list[str] = field(default_factory=list)
    user_question: str = ""
    selected_template: str = "general"
    metadata: dict[str, Any] = field(default_factory=dict)

    def sanitized(self) -> "StrategyContext":
        data = asdict(self)
        data["strategy_text"] = redact_sensitive_text(data.get("strategy_text", ""))
        data["user_question"] = redact_sensitive_text(data.get("user_question", ""))
        data["validation_messages"] = [
            redact_sensitive_text(coerce_text(message))
            for message in data.get("validation_messages", [])
        ]
        data["backtest_summary"] = compact_mapping(data.get("backtest_summary", {}))
        data["metadata"] = compact_mapping(data.get("metadata", {}))
        return StrategyContext(**data)

    def to_dict(self, *, sanitize: bool = True) -> dict[str, Any]:
        ctx = self.sanitized() if sanitize else self
        return asdict(ctx)

    def to_json(self, *, sanitize: bool = True, indent: int = 2) -> str:
        return json.dumps(
            self.to_dict(sanitize=sanitize),
            indent=indent,
            sort_keys=True,
            default=str,
        )

    def to_markdown(
        self,
        *,
        sanitize: bool = True,
        max_strategy_chars: int = 12000,
    ) -> str:
        ctx = self.sanitized() if sanitize else self
        strategy = truncate_text(
            ctx.strategy_text,
            max_strategy_chars,
            label="strategy_text",
        ).strip()

        lines: list[str] = [
            "# Strategy Context",
            "",
            f"- Schema: `{ctx.schema_version}`",
            f"- Created: `{ctx.created_at}`",
            f"- Source: `{ctx.source}`",
            "",
            "## Market / Replay",
            "",
            f"- Symbol: `{ctx.symbol or 'not selected'}`",
            f"- Timeframe: `{ctx.timeframe or 'not selected'}`",
            f"- Start: `{ctx.start or 'not selected'}`",
            f"- End: `{ctx.end or 'not selected'}`",
            "",
            "## Backtest Inputs",
            "",
            f"- Initial cash: `{ctx.initial_cash}`",
            f"- Quantity: `{ctx.quantity}`",
            f"- Commission: `{ctx.commission}`",
            f"- Slippage: `{ctx.slippage}`",
            "",
            "## Strategy Code",
            "",
            "```text",
            strategy or "[empty]",
            "```",
            "",
            "## Backtest Summary",
            "",
        ]

        if ctx.backtest_summary:
            for key, value in ctx.backtest_summary.items():
                lines.append(f"- {key}: `{value}`")
        else:
            lines.append("- No backtest summary attached.")

        lines.extend(["", "## Validation Messages", ""])

        if ctx.validation_messages:
            for message in ctx.validation_messages:
                lines.append(f"- {message}")
        else:
            lines.append("- No validation messages attached.")

        if ctx.user_question:
            lines.extend(["", "## User Question", "", ctx.user_question.strip()])

        return "\n".join(lines).rstrip() + "\n"

    def to_ai_context(
        self,
        *,
        max_strategy_chars: int = 12000,
        max_total_chars: int = 24000,
    ) -> str:
        """Return sanitized Markdown suitable for advisory-only LLM context."""
        markdown = self.to_markdown(
            sanitize=True,
            max_strategy_chars=max_strategy_chars,
        )
        return truncate_text(markdown, max_total_chars, label="ai_context")

    def preview(self, *, max_chars: int = 2000) -> str:
        ctx = self.sanitized()
        summary = [
            "Strategy Context Preview",
            f"Symbol: {ctx.symbol or 'not selected'}",
            f"Timeframe: {ctx.timeframe or 'not selected'}",
            f"Range: {ctx.start or '?'} -> {ctx.end or '?'}",
            f"Strategy chars: {len(ctx.strategy_text)}",
            f"Backtest summary keys: {', '.join(ctx.backtest_summary.keys()) or 'none'}",
            f"Validation messages: {len(ctx.validation_messages)}",
        ]
        if ctx.user_question:
            summary.append(f"Question: {ctx.user_question}")
        return truncate_text("\n".join(summary), max_chars, label="preview")


def build_strategy_context(
    *,
    symbol: Any = "",
    timeframe: Any = "",
    start: Any = "",
    end: Any = "",
    strategy_name: Any = "",
    strategy_text: Any = "",
    initial_cash: Any = None,
    quantity: Any = None,
    commission: Any = None,
    slippage: Any = None,
    backtest_summary: Mapping[str, Any] | None = None,
    validation_messages: list[Any] | tuple[Any, ...] | None = None,
    user_question: Any = "",
    selected_template: Any = "general",
    metadata: Mapping[str, Any] | None = None,
    source: str = "strategy_lab",
) -> StrategyContext:
    return StrategyContext(
        source=coerce_text(source, "strategy_lab"),
        symbol=coerce_text(symbol).upper().strip(),
        timeframe=coerce_text(timeframe).strip(),
        start=coerce_text(start).strip(),
        end=coerce_text(end).strip(),
        strategy_name=coerce_text(strategy_name).strip(),
        strategy_text=coerce_text(strategy_text),
        initial_cash=coerce_number(initial_cash),
        quantity=coerce_number(quantity),
        commission=coerce_number(commission),
        slippage=coerce_number(slippage),
        backtest_summary=compact_mapping(backtest_summary),
        validation_messages=[
            redact_sensitive_text(coerce_text(message))
            for message in (validation_messages or [])
            if coerce_text(message).strip()
        ],
        user_question=coerce_text(user_question).strip(),
        selected_template=coerce_text(selected_template, "general").strip() or "general",
        metadata=compact_mapping(metadata),
    )


def write_context_exports(
    context: StrategyContext,
    *,
    output_dir: str | Path,
    stem: str = "strategy_context",
) -> dict[str, Path]:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    safe_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem).strip("_") or "strategy_context"
    json_path = out_dir / f"{safe_stem}.json"
    md_path = out_dir / f"{safe_stem}.md"

    json_path.write_text(context.to_json(sanitize=True), encoding="utf-8")
    md_path.write_text(context.to_markdown(sanitize=True), encoding="utf-8")

    return {"json": json_path, "markdown": md_path}


def build_ai_prompt_with_context(
    *,
    context: StrategyContext,
    user_question: str,
    instruction: str = "",
) -> str:
    """
    Combine a sanitized strategy context snapshot with a user question.

    This is intentionally text-only. It does not grant broker access, order access,
    file access, network access, or tool execution.
    """
    base_instruction = instruction.strip() or (
        "You are an advisory-only strategy assistant. "
        "Explain observations, risks, and possible improvements. "
        "Do not provide order-placement instructions or claim certainty."
    )

    ctx = context.sanitized()
    ctx.user_question = redact_sensitive_text(user_question)

    return (
        f"{base_instruction}\n\n"
        f"{ctx.to_ai_context()}\n\n"
        "## Advisor Task\n\n"
        f"{redact_sensitive_text(user_question).strip()}\n"
    )
