"""
No-op LLM provider.

Used when AI features are disabled or no provider is configured.
"""

from __future__ import annotations

from typing import Any

from services.llm.base import LLMMessage, LLMProvider, LLMResponse


class NoOpLLMProvider(LLMProvider):
    name = "none"

    def __init__(self, reason: str = "LLM provider is disabled.") -> None:
        self.reason = reason

    def generate(
        self,
        messages: list[LLMMessage] | list[dict[str, str]],
        *,
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_output_tokens: int | None = None,
    ) -> LLMResponse:
        return LLMResponse(
            content=(
                "LLM provider is disabled. "
                "This is expected when AI_FEATURES_ENABLED=false or LLM_PROVIDER=none."
            ),
            provider=self.name,
            model="none",
            metadata={
                "enabled": False,
                "reason": self.reason,
            },
        )

    def describe(self) -> dict[str, Any]:
        data = super().describe()
        data.update(
            {
                "enabled": False,
                "reason": self.reason,
            }
        )
        return data
