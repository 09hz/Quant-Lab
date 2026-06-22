"""
OpenAI-compatible chat provider.

Works with services that expose a /chat/completions-style endpoint, including
OpenAI-compatible local model servers. This provider is text-only and advisory-only.
It does not define tools, broker access, or order placement.

Patch 12b adds:
- automatic max_tokens vs max_completion_tokens handling
- one safe retry when OpenAI reports an unsupported parameter
- friendly structured HTTP errors for diagnostics scripts
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from services.llm.base import LLMMessage, LLMProvider, LLMResponse, normalize_messages


@dataclass
class LLMProviderHTTPError(RuntimeError):
    """Structured HTTP error for LLM provider diagnostics."""

    status_code: int
    endpoint: str
    detail: str = ""
    error_code: str = ""
    error_type: str = ""
    error_message: str = ""

    def __post_init__(self) -> None:
        RuntimeError.__init__(
            self,
            f"LLM HTTP error {self.status_code} from {self.endpoint}. {self.detail}",
        )


class OpenAICompatibleLLMProvider(LLMProvider):
    name = "openai-compatible"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str = "",
        model: str,
        timeout: float = 60,
        max_input_chars: int = 8000,
    ) -> None:
        self.base_url = str(base_url or "").strip().rstrip("/")
        self.api_key = str(api_key or "").strip()
        self.model = str(model or "").strip()
        self.timeout = float(timeout or 60)
        self.max_input_chars = int(max_input_chars or 8000)

        if not self.base_url:
            raise ValueError("LLM_BASE_URL is required for OpenAI-compatible providers.")

        if not self.model:
            raise ValueError("LLM_MODEL is required for OpenAI-compatible providers.")

    @property
    def endpoint(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/chat/completions"

    def generate(
        self,
        messages: list[LLMMessage] | list[dict[str, str]],
        *,
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_output_tokens: int | None = None,
    ) -> LLMResponse:
        normalized_messages = normalize_messages(
            messages,
            system_prompt=system_prompt,
            max_input_chars=self.max_input_chars,
        )

        payload = self._build_payload(
            normalized_messages,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

        # Retry only for provider-reported parameter incompatibilities.
        # This keeps support for OpenAI newer models and OpenAI-compatible local servers.
        for _attempt in range(3):
            try:
                raw_text = self._post_json(payload)
                break
            except LLMProviderHTTPError as exc:
                if self._maybe_repair_payload_for_unsupported_parameter(payload, exc):
                    continue
                raise
        else:
            raise RuntimeError("LLM provider failed after compatibility retries.")

        raw = json.loads(raw_text) if raw_text else {}
        content = self._extract_content(raw)

        return LLMResponse(
            content=content,
            provider=self.name,
            model=self.model,
            metadata={
                "endpoint": self.endpoint,
                "base_url": self.base_url,
                "token_limit_parameter": self._token_limit_parameter(),
            },
            raw=raw,
        )

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "class": self.__class__.__name__,
            "base_url": self.base_url,
            "endpoint": self.endpoint,
            "model": self.model,
            "api_key_configured": bool(self.api_key),
            "timeout": self.timeout,
            "max_input_chars": self.max_input_chars,
            "token_limit_parameter": self._token_limit_parameter(),
            "temperature_mode": self._temperature_mode(),
        }

    def _build_payload(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float,
        max_output_tokens: int | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }

        if self._should_send_temperature():
            payload["temperature"] = float(temperature)

        if max_output_tokens is not None:
            payload[self._token_limit_parameter()] = int(max_output_tokens)

        return payload

    def _post_json(self, payload: dict[str, Any]) -> str:
        body = json.dumps(payload).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        request = Request(
            self.endpoint,
            data=body,
            headers=headers,
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                return response.read().decode("utf-8")
        except HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8")[:2000]
            except Exception:
                detail = ""

            error_payload = self._parse_error_detail(detail)
            raise LLMProviderHTTPError(
                status_code=exc.code,
                endpoint=self.endpoint,
                detail=detail,
                error_code=str(error_payload.get("code", "") or ""),
                error_type=str(error_payload.get("type", "") or ""),
                error_message=str(error_payload.get("message", "") or ""),
            ) from exc
        except URLError as exc:
            raise RuntimeError(f"LLM connection failed for {self.endpoint}: {exc}") from exc

    def _maybe_repair_payload_for_unsupported_parameter(
        self,
        payload: dict[str, Any],
        exc: LLMProviderHTTPError,
    ) -> bool:
        text = " ".join(
            [
                exc.detail or "",
                exc.error_message or "",
                exc.error_code or "",
                exc.error_type or "",
            ]
        ).lower()

        if "unsupported parameter" not in text:
            return False

        if "max_tokens" in text and "max_completion_tokens" in text and "max_tokens" in payload:
            payload["max_completion_tokens"] = payload.pop("max_tokens")
            return True

        if (
            "max_completion_tokens" in text
            and "max_tokens" in text
            and "max_completion_tokens" in payload
        ):
            payload["max_tokens"] = payload.pop("max_completion_tokens")
            return True

        if "temperature" in text and "temperature" in payload:
            payload.pop("temperature", None)
            return True

        return False

    def _token_limit_parameter(self) -> str:
        configured = str(os.getenv("LLM_CHAT_TOKEN_PARAM", "auto") or "auto").strip().lower()

        if configured in {"max_tokens", "max_completion_tokens"}:
            return configured

        model = self.model.lower()

        # Newer OpenAI reasoning/GPT-5-family chat models reject max_tokens and expect
        # max_completion_tokens. Local OpenAI-compatible servers often still accept max_tokens,
        # so this remains auto-detected and repairable.
        if model.startswith(("gpt-5", "o1", "o3", "o4")):
            return "max_completion_tokens"

        return "max_tokens"

    def _temperature_mode(self) -> str:
        return str(os.getenv("LLM_SEND_TEMPERATURE", "auto") or "auto").strip().lower()

    def _should_send_temperature(self) -> bool:
        mode = self._temperature_mode()

        if mode in {"0", "false", "no", "off", "never"}:
            return False

        if mode in {"1", "true", "yes", "on", "always"}:
            return True

        # Auto mode: many newer reasoning-family models only support default sampling.
        model = self.model.lower()
        if model.startswith(("gpt-5", "o1", "o3", "o4")):
            return False

        return True

    def _parse_error_detail(self, detail: str) -> dict[str, Any]:
        try:
            parsed = json.loads(detail)
        except Exception:
            return {}

        if isinstance(parsed, dict):
            error = parsed.get("error")
            if isinstance(error, dict):
                return error

        return {}

    def _extract_content(self, raw: dict[str, Any]) -> str:
        choices = raw.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                message = first.get("message")
                if isinstance(message, dict):
                    content = message.get("content")
                    if isinstance(content, str):
                        return content

                    # Some providers return structured content parts.
                    if isinstance(content, list):
                        parts: list[str] = []
                        for item in content:
                            if isinstance(item, dict):
                                text = item.get("text")
                                if isinstance(text, str):
                                    parts.append(text)
                        if parts:
                            return "".join(parts)

                text = first.get("text")
                if isinstance(text, str):
                    return text

        output_text = raw.get("output_text")
        if isinstance(output_text, str):
            return output_text

        return ""
