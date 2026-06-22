"""
Central AI safety policy.

This module is intentionally dependency-light and reads only environment
variables. Future AI tools, LLM adapters, and broker-facing assistants should
check this policy before using external tools, broker data, or order routing.

Safe default:
    AI is disabled.
    Advisory-only mode is true.
    AI order placement is false.
    AI broker access is false.
    AI external tools are false.
    Human confirmation is required.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from typing import Any


_TRUE_VALUES = {"1", "true", "yes", "y", "on"}
_FALSE_VALUES = {"0", "false", "no", "n", "off"}


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return default

    value = str(raw).strip().lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False

    # Unknown bool strings fall back to the safe default.
    return default


def _env_text(name: str, default: str = "") -> str:
    return str(os.getenv(name, default) or default).strip()


@dataclass(frozen=True)
class AISafetyDecision:
    allowed: bool
    reason: str
    required_human_confirmation: bool = True
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class AISafetyPolicy:
    ai_features_enabled: bool = False
    ai_advisory_only: bool = True
    ai_allow_order_placement: bool = False
    ai_allow_broker_access: bool = False
    ai_allow_external_tools: bool = False
    ai_require_human_confirmation: bool = True
    llm_provider: str = "none"
    llm_base_url_configured: bool = False
    openai_api_key_configured: bool = False

    @classmethod
    def from_env(cls) -> "AISafetyPolicy":
        return cls(
            ai_features_enabled=_env_bool("AI_FEATURES_ENABLED", False),
            ai_advisory_only=_env_bool("AI_ADVISORY_ONLY", True),
            ai_allow_order_placement=_env_bool("AI_ALLOW_ORDER_PLACEMENT", False),
            ai_allow_broker_access=_env_bool("AI_ALLOW_BROKER_ACCESS", False),
            ai_allow_external_tools=_env_bool("AI_ALLOW_EXTERNAL_TOOLS", False),
            ai_require_human_confirmation=_env_bool("AI_REQUIRE_HUMAN_CONFIRMATION", True),
            llm_provider=_env_text("LLM_PROVIDER", "none").lower() or "none",
            llm_base_url_configured=bool(_env_text("LLM_BASE_URL", "")),
            openai_api_key_configured=bool(_env_text("OPENAI_API_KEY", "")),
        )

    def to_safe_dict(self) -> dict[str, Any]:
        """Return a display-safe representation. No secrets are included."""
        data = asdict(self)
        data["effective_mode"] = self.effective_mode
        data["violations"] = self.validate_configuration()
        return data

    @property
    def effective_mode(self) -> str:
        if not self.ai_features_enabled:
            return "disabled"
        if self.ai_advisory_only:
            return "advisory_only"
        if self.ai_allow_order_placement:
            return "order_capable_requires_confirmation"
        if self.ai_allow_broker_access or self.ai_allow_external_tools:
            return "tool_capable_no_orders"
        return "enabled_no_tools"

    def validate_configuration(self) -> list[str]:
        issues: list[str] = []

        if not self.ai_features_enabled:
            if self.ai_allow_order_placement:
                issues.append("AI_ALLOW_ORDER_PLACEMENT=true while AI_FEATURES_ENABLED=false.")
            if self.ai_allow_broker_access:
                issues.append("AI_ALLOW_BROKER_ACCESS=true while AI_FEATURES_ENABLED=false.")
            if self.ai_allow_external_tools:
                issues.append("AI_ALLOW_EXTERNAL_TOOLS=true while AI_FEATURES_ENABLED=false.")

        if self.ai_advisory_only and self.ai_allow_order_placement:
            issues.append("AI_ADVISORY_ONLY=true conflicts with AI_ALLOW_ORDER_PLACEMENT=true.")

        if self.ai_allow_order_placement and not self.ai_allow_broker_access:
            issues.append("AI order placement requires AI_ALLOW_BROKER_ACCESS=true.")

        if self.ai_allow_order_placement and not self.ai_require_human_confirmation:
            issues.append("AI order placement requires AI_REQUIRE_HUMAN_CONFIRMATION=true.")

        if self.llm_provider in {"openai", "openai-compatible"} and not self.openai_api_key_configured:
            issues.append("LLM_PROVIDER requires OPENAI_API_KEY, but no key is configured.")

        if self.llm_provider in {"ollama", "lmstudio", "lm-studio", "openai-compatible"} and not self.llm_base_url_configured:
            issues.append("Selected LLM provider usually requires LLM_BASE_URL, but it is empty.")

        return issues

    def can_use_llm(self) -> AISafetyDecision:
        if not self.ai_features_enabled:
            return AISafetyDecision(False, "AI features are disabled.")

        if self.llm_provider in {"", "none", "disabled"}:
            return AISafetyDecision(False, "No LLM provider is configured.")

        issues = self.validate_configuration()
        if issues:
            return AISafetyDecision(False, "AI safety configuration has issues.", metadata={"issues": issues})

        return AISafetyDecision(
            True,
            "LLM use is allowed under the current policy.",
            required_human_confirmation=self.ai_require_human_confirmation,
        )

    def can_access_broker(self) -> AISafetyDecision:
        if not self.ai_features_enabled:
            return AISafetyDecision(False, "AI features are disabled.")

        if not self.ai_allow_broker_access:
            return AISafetyDecision(False, "AI broker access is disabled.")

        if self.ai_advisory_only:
            return AISafetyDecision(False, "AI advisory-only mode blocks broker access.")

        issues = self.validate_configuration()
        if issues:
            return AISafetyDecision(False, "AI safety configuration has issues.", metadata={"issues": issues})

        return AISafetyDecision(
            True,
            "AI broker access is allowed under the current policy.",
            required_human_confirmation=self.ai_require_human_confirmation,
        )

    def can_place_order(self) -> AISafetyDecision:
        if not self.ai_features_enabled:
            return AISafetyDecision(False, "AI features are disabled.")

        if self.ai_advisory_only:
            return AISafetyDecision(False, "AI advisory-only mode blocks order placement.")

        if not self.ai_allow_order_placement:
            return AISafetyDecision(False, "AI order placement is disabled.")

        if not self.ai_allow_broker_access:
            return AISafetyDecision(False, "AI broker access is disabled.")

        if not self.ai_require_human_confirmation:
            return AISafetyDecision(False, "Human confirmation is required for AI order placement.")

        issues = self.validate_configuration()
        if issues:
            return AISafetyDecision(False, "AI safety configuration has issues.", metadata={"issues": issues})

        return AISafetyDecision(
            True,
            "AI order placement is policy-allowed, but still requires a human confirmation workflow.",
            required_human_confirmation=True,
        )

    def assert_can_use_llm(self) -> None:
        decision = self.can_use_llm()
        if not decision.allowed:
            raise PermissionError(decision.reason)

    def assert_can_access_broker(self) -> None:
        decision = self.can_access_broker()
        if not decision.allowed:
            raise PermissionError(decision.reason)

    def assert_can_place_order(self) -> None:
        decision = self.can_place_order()
        if not decision.allowed:
            raise PermissionError(decision.reason)


def get_ai_safety_policy() -> AISafetyPolicy:
    return AISafetyPolicy.from_env()
