"""
Factory for advisory LLM providers.

The factory enforces the central AI safety policy by default. When the policy
does not allow LLM use, it returns NoOpLLMProvider instead of raising.
"""

from __future__ import annotations

import os
from typing import Any

from services.llm.base import LLMProvider
from services.llm.noop_provider import NoOpLLMProvider
from services.llm.openai_compatible_provider import OpenAICompatibleLLMProvider
from services.safety.ai_policy import get_ai_safety_policy


def _env_text(name: str, default: str = "") -> str:
    return str(os.getenv(name, default) or default).strip()


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def get_llm_provider_name(default: str = "none") -> str:
    return _env_text("LLM_PROVIDER", default).lower() or default


def build_llm_provider(
    *,
    provider_name: str | None = None,
    enforce_policy: bool = True,
) -> LLMProvider:
    """
    Build the configured advisory LLM provider.

    Safe default:
        If AI is disabled or policy blocks LLM use, return NoOpLLMProvider.
    """
    policy = get_ai_safety_policy()
    provider = str(provider_name or get_llm_provider_name(policy.llm_provider)).strip().lower()

    if provider in {"", "none", "disabled", "off"}:
        return NoOpLLMProvider(reason="LLM_PROVIDER is none/disabled.")

    if enforce_policy:
        decision = policy.can_use_llm()
        if not decision.allowed:
            return NoOpLLMProvider(reason=decision.reason)

    if provider in {"openai", "openai-compatible", "openai_compatible"}:
        base_url = _env_text("LLM_BASE_URL", "")
        if provider == "openai" and not base_url:
            base_url = "https://api.openai.com/v1"

        api_key = _env_text("LLM_API_KEY", "") or _env_text("OPENAI_API_KEY", "")
        return OpenAICompatibleLLMProvider(
            base_url=base_url,
            api_key=api_key,
            model=_env_text("LLM_MODEL", ""),
            timeout=_env_float("LLM_TIMEOUT_SECONDS", 60),
            max_input_chars=_env_int("LLM_MAX_INPUT_CHARS", 8000),
        )

    if provider in {"ollama", "local-ollama"}:
        return OpenAICompatibleLLMProvider(
            base_url=_env_text("LLM_BASE_URL", "http://127.0.0.1:11434/v1"),
            api_key=_env_text("LLM_API_KEY", ""),
            model=_env_text("LLM_MODEL", ""),
            timeout=_env_float("LLM_TIMEOUT_SECONDS", 60),
            max_input_chars=_env_int("LLM_MAX_INPUT_CHARS", 8000),
        )

    if provider in {"lmstudio", "lm-studio", "lm_studio"}:
        return OpenAICompatibleLLMProvider(
            base_url=_env_text("LLM_BASE_URL", "http://127.0.0.1:1234/v1"),
            api_key=_env_text("LLM_API_KEY", ""),
            model=_env_text("LLM_MODEL", ""),
            timeout=_env_float("LLM_TIMEOUT_SECONDS", 60),
            max_input_chars=_env_int("LLM_MAX_INPUT_CHARS", 8000),
        )

    return NoOpLLMProvider(reason=f"Unsupported LLM_PROVIDER={provider!r}.")


def describe_llm_provider(provider: LLMProvider | None = None) -> dict[str, Any]:
    if provider is None:
        provider = build_llm_provider()
    return provider.describe()
