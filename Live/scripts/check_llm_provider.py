from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


LIVE_ROOT = Path(__file__).resolve().parents[1]
if str(LIVE_ROOT) not in sys.path:
    sys.path.insert(0, str(LIVE_ROOT))

from services.llm.openai_compatible_provider import LLMProviderHTTPError  # noqa: E402
from services.llm.provider_factory import build_llm_provider, describe_llm_provider  # noqa: E402
from services.safety.ai_policy import get_ai_safety_policy  # noqa: E402


def _print_policy() -> None:
    policy = get_ai_safety_policy()
    print("AI Safety Policy")
    print(f"  Effective mode: {policy.effective_mode}")
    print(f"  AI_FEATURES_ENABLED: {policy.ai_features_enabled}")
    print(f"  AI_ADVISORY_ONLY: {policy.ai_advisory_only}")
    print(f"  AI_ALLOW_ORDER_PLACEMENT: {policy.ai_allow_order_placement}")
    print(f"  AI_ALLOW_BROKER_ACCESS: {policy.ai_allow_broker_access}")
    print(f"  AI_REQUIRE_HUMAN_CONFIRMATION: {policy.ai_require_human_confirmation}")
    print(f"  Can use LLM: {policy.can_use_llm().allowed} -- {policy.can_use_llm().reason}")


def _print_friendly_error(exc: Exception) -> None:
    print("")
    print("[ERROR] LLM generation failed.")

    if isinstance(exc, LLMProviderHTTPError):
        print(f"  HTTP status: {exc.status_code}")
        if exc.error_code:
            print(f"  Error code: {exc.error_code}")
        if exc.error_type:
            print(f"  Error type: {exc.error_type}")
        if exc.error_message:
            print(f"  Message: {exc.error_message}")

        code = (exc.error_code or "").lower()
        message = (exc.error_message or exc.detail or "").lower()

        print("")
        print("Suggested fix:")

        if exc.status_code == 401:
            print("  Check OPENAI_API_KEY. The key is missing, invalid, or from the wrong project.")
        elif code == "insufficient_quota" or "insufficient_quota" in message:
            print("  Check OpenAI API billing, project budget, and quota.")
        elif code == "model_not_found" or ("model" in message and "does not exist" in message):
            print("  Set LLM_MODEL to a model your API project can access.")
        elif "unsupported parameter" in message and "max_tokens" in message:
            print("  This model expects max_completion_tokens. Patch 12b can auto-handle this.")
            print('  You can also set: $env:LLM_CHAT_TOKEN_PARAM="max_completion_tokens"')
        elif "unsupported parameter" in message and "temperature" in message:
            print("  This model may not support temperature. Set LLM_SEND_TEMPERATURE=false.")
        elif exc.status_code == 429:
            print("  You are rate-limited or out of quota. Check RPM/TPM/billing.")
        else:
            print("  Review the provider settings above and the error message.")

        return

    print(f"  {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check advisory LLM provider configuration.")
    parser.add_argument("--provider", default=None, help="Override LLM_PROVIDER for this check.")
    parser.add_argument("--prompt", default="", help="Optional prompt to send to the LLM.")
    parser.add_argument("--system-prompt", default="", help="Optional system prompt.")
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--max-output-tokens", type=int, default=None)
    parser.add_argument("--json", action="store_true", help="Print provider metadata as JSON.")
    args = parser.parse_args()

    provider = build_llm_provider(provider_name=args.provider, enforce_policy=True)
    provider_info = describe_llm_provider(provider)

    if args.json:
        payload = {
            "provider": provider_info,
            "policy": get_ai_safety_policy().to_safe_dict(),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    print("LLM Provider Check")
    print("")
    _print_policy()
    print("")
    print("Provider")
    for key, value in provider_info.items():
        print(f"  {key}: {value}")

    if not args.prompt:
        print("")
        print("No prompt sent. Use --prompt to test generation when AI policy allows it.")
        return 0

    print("")
    print("Sending advisory prompt...")

    try:
        response = provider.generate(
            [{"role": "user", "content": args.prompt}],
            system_prompt=args.system_prompt or None,
            temperature=args.temperature,
            max_output_tokens=args.max_output_tokens,
        )
    except Exception as exc:
        _print_friendly_error(exc)
        return 2

    print("")
    print("Response")
    print(f"  provider: {response.provider}")
    print(f"  model: {response.model}")
    print("")
    print(response.content)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
