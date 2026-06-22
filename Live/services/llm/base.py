"""
Base interfaces for LLM providers.

This layer is intentionally advisory-only. It does not expose broker objects,
order placement, account data, or external tools.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class LLMMessage:
    role: str
    content: str


@dataclass(frozen=True)
class LLMResponse:
    content: str
    provider: str
    model: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] | None = None


class LLMProvider(ABC):
    """Abstract interface for advisory LLM providers."""

    name = "base"

    @abstractmethod
    def generate(
        self,
        messages: list[LLMMessage] | list[dict[str, str]],
        *,
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_output_tokens: int | None = None,
    ) -> LLMResponse:
        """Generate an advisory text response."""

    def describe(self) -> dict[str, Any]:
        """Return display-safe provider metadata."""
        return {
            "name": self.name,
            "class": self.__class__.__name__,
        }


def normalize_messages(
    messages: list[LLMMessage] | list[dict[str, str]] | str,
    *,
    system_prompt: str | None = None,
    max_input_chars: int | None = None,
) -> list[dict[str, str]]:
    """Normalize messages to a compact OpenAI-compatible chat format."""
    normalized: list[dict[str, str]] = []

    if system_prompt:
        normalized.append({"role": "system", "content": str(system_prompt)})

    if isinstance(messages, str):
        normalized.append({"role": "user", "content": messages})
    else:
        for item in messages:
            if isinstance(item, LLMMessage):
                role = item.role
                content = item.content
            else:
                role = str(item.get("role", "user"))
                content = str(item.get("content", ""))

            role = role.strip().lower()
            if role not in {"system", "user", "assistant"}:
                role = "user"

            if content.strip():
                normalized.append({"role": role, "content": content})

    if max_input_chars and max_input_chars > 0:
        total = 0
        trimmed_reversed: list[dict[str, str]] = []

        for message in reversed(normalized):
            content = message["content"]
            remaining = max_input_chars - total
            if remaining <= 0:
                break

            if len(content) > remaining:
                content = content[-remaining:]

            total += len(content)
            trimmed_reversed.append({"role": message["role"], "content": content})

        normalized = list(reversed(trimmed_reversed))

    if not normalized:
        normalized.append({"role": "user", "content": "Hello."})

    return normalized
