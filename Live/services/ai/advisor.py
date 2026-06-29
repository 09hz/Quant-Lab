"""
Advisory-only AI assistant service.

This module is intentionally read-only:
- no broker objects
- no order placement
- no account access
- no external tool calls
- no browser-stored secrets

Future UI callbacks should call this service instead of calling an LLM provider
directly, so the central AI safety policy remains the single gate.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
import os
import re
from typing import Any

from services.llm.provider_factory import build_llm_provider, describe_llm_provider
from services.safety.ai_policy import AISafetyDecision, get_ai_safety_policy


_SECRET_PATTERNS = [
    re.compile(r"(sk-[A-Za-z0-9_\-]{20,})"),
    re.compile(r"(?i)(api[_\- ]?key\s*[:=]\s*)([^\s,;]+)"),
    re.compile(r"(?i)(bearer\s+)([A-Za-z0-9_\-\.]+)"),
]


DEFAULT_SYSTEM_PROMPT = """You are an advisory-only assistant inside a trading research app.

Safety rules:
- Do not place orders.
- Do not claim to have placed, modified, or canceled trades.
- Do not request API keys, passwords, broker tokens, or account secrets.
- Do not provide instructions that bypass broker, risk, or human-confirmation gates.
- You may explain chart signals, indicators, backtest results, logs, and code behavior.
- Make uncertainty clear.
- Keep answers practical and concise.
"""


@dataclass(frozen=True)
class AIAdvisorRequest:
    prompt: str
    context: str = ""
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    max_output_tokens: int | None = None
    temperature: float = 0.2


@dataclass(frozen=True)
class AIAdvisorResult:
    ok: bool
    blocked: bool
    content: str
    reason: str = ""
    provider: str = ""
    model: str = ""
    created_at: str = ""
    policy: dict[str, Any] = field(default_factory=dict)
    provider_info: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_safe_dict(self) -> dict[str, Any]:
        """Return display-safe metadata. No secrets are included."""
        return asdict(self)


class AIAdvisorService:
    """
    Advisory AI facade.

    UI code and scripts should use this facade instead of directly calling an
    LLM provider. That keeps future AI features behind one policy boundary.
    """

    def __init__(self) -> None:
        self.max_context_chars = _env_int("AI_ADVISOR_MAX_CONTEXT_CHARS", 6000)
        self.default_max_output_tokens = _env_int("AI_ADVISOR_MAX_OUTPUT_TOKENS", 500)

    def ask(
        self,
        prompt: str,
        *,
        context: str = "",
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        max_output_tokens: int | None = None,
        temperature: float = 0.2,
        max_context_chars: int | None = None,
    ) -> AIAdvisorResult:
        created_at = datetime.now().isoformat(timespec="seconds")
        policy = get_ai_safety_policy()
        decision = policy.can_use_llm()

        safe_policy = policy.to_safe_dict()
        if not decision.allowed:
            return AIAdvisorResult(
                ok=False,
                blocked=True,
                content="",
                reason=decision.reason,
                created_at=created_at,
                policy=safe_policy,
                metadata={"decision": _decision_to_dict(decision)},
            )

        cleaned_prompt = _redact_secrets(str(prompt or "").strip())
        cleaned_context = _redact_secrets(str(context or "").strip())

        if not cleaned_prompt:
            return AIAdvisorResult(
                ok=False,
                blocked=True,
                content="",
                reason="Prompt is empty.",
                created_at=created_at,
                policy=safe_policy,
                metadata={"decision": _decision_to_dict(decision)},
            )

        effective_max_context_chars = self.max_context_chars
        if max_context_chars is not None:
            try:
                effective_max_context_chars = int(max_context_chars)
            except Exception:
                effective_max_context_chars = self.max_context_chars

        if effective_max_context_chars > 0 and len(cleaned_context) > effective_max_context_chars:
            cleaned_context = cleaned_context[-effective_max_context_chars :]

        provider = build_llm_provider(enforce_policy=True)
        provider_info = describe_llm_provider(provider)

        if getattr(provider, "name", "") in {"none", "disabled", "off"}:
            return AIAdvisorResult(
                ok=False,
                blocked=True,
                content="",
                reason=str(getattr(provider, "reason", "LLM provider is disabled.")),
                provider=getattr(provider, "name", "none"),
                created_at=created_at,
                policy=safe_policy,
                provider_info=provider_info,
                metadata={"decision": _decision_to_dict(decision)},
            )

        messages = _build_messages(cleaned_prompt, cleaned_context)
        token_limit = max_output_tokens if max_output_tokens is not None else self.default_max_output_tokens

        try:
            response = provider.generate(
                messages,
                system_prompt=system_prompt,
                temperature=temperature,
                max_output_tokens=token_limit,
            )
        except Exception as exc:
            return AIAdvisorResult(
                ok=False,
                blocked=False,
                content="",
                reason=_friendly_llm_exception_message(exc),
                provider=getattr(provider, "name", provider.__class__.__name__),
                model=str(getattr(provider, "model", "")),
                created_at=created_at,
                policy=safe_policy,
                provider_info=provider_info,
                metadata={
                    "exception_type": exc.__class__.__name__,
                    "decision": _decision_to_dict(decision),
                },
            )

        return AIAdvisorResult(
            ok=True,
            blocked=False,
            content=str(response.content or "").strip(),
            reason="AI advisory response generated.",
            provider=response.provider,
            model=response.model,
            created_at=created_at,
            policy=safe_policy,
            provider_info=provider_info,
            metadata={
                "response_metadata": dict(response.metadata or {}),
                "decision": _decision_to_dict(decision),
            },
        )


def build_ai_advisor_service() -> AIAdvisorService:
    return AIAdvisorService()


def ask_ai_advisor(
    prompt: str,
    *,
    context: str = "",
    max_output_tokens: int | None = None,
    temperature: float = 0.2,
    max_context_chars: int | None = None,
) -> AIAdvisorResult:
    return build_ai_advisor_service().ask(
        prompt,
        context=context,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
        max_context_chars=max_context_chars,
    )


def _build_messages(prompt: str, context: str) -> list[dict[str, str]]:
    if context:
        return [
            {
                "role": "user",
                "content": (
                    "Use the following app context as read-only information. "
                    "Do not infer broker/account access from it.\n\n"
                    f"CONTEXT:\n{context}\n\nQUESTION:\n{prompt}"
                ),
            }
        ]

    return [{"role": "user", "content": prompt}]


def _redact_secrets(value: str) -> str:
    redacted = value
    for pattern in _SECRET_PATTERNS:
        if pattern.groups >= 2:
            redacted = pattern.sub(lambda m: f"{m.group(1)}[REDACTED]", redacted)
        else:
            redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def _friendly_llm_exception_message(exc: Exception) -> str:
    status_code = getattr(exc, "status_code", None)
    error_code = str(getattr(exc, "error_code", "") or "")
    error_message = str(getattr(exc, "error_message", "") or "")
    detail = str(getattr(exc, "detail", "") or "")

    if status_code == 401:
        return "LLM request was unauthorized. Check the API key for the selected provider."

    if status_code == 404:
        return "LLM model or endpoint was not found. Check LLM_MODEL and LLM_BASE_URL."

    if status_code == 429:
        if error_code == "insufficient_quota":
            return "LLM quota is unavailable. Check API billing, project budget, and usage limits."
        return "LLM rate limit was reached. Lower request frequency or token limits."

    if status_code:
        return f"LLM HTTP error {status_code}. {error_message or detail}".strip()

    text = str(exc)
    if "insufficient_quota" in text:
        return "LLM quota is unavailable. Check API billing, project budget, and usage limits."
    if "model_not_found" in text:
        return "LLM model was not found or is unavailable to this API key."
    return text or exc.__class__.__name__


def _decision_to_dict(decision: AISafetyDecision) -> dict[str, Any]:
    return {
        "allowed": decision.allowed,
        "reason": decision.reason,
        "required_human_confirmation": decision.required_human_confirmation,
        "metadata": decision.metadata or {},
    }


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default
