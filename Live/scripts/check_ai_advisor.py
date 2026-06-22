from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


LIVE_ROOT = Path(__file__).resolve().parents[1]
if str(LIVE_ROOT) not in sys.path:
    sys.path.insert(0, str(LIVE_ROOT))

try:
    from services.config.env_loader import load_app_env  # noqa: E402

    load_app_env(override=True, verbose=False)
except Exception:
    pass

from services.ai.advisor import ask_ai_advisor  # noqa: E402
from services.llm.provider_factory import build_llm_provider, describe_llm_provider  # noqa: E402
from services.safety.ai_policy import get_ai_safety_policy  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a safe advisory-only AI assistant smoke test."
    )
    parser.add_argument(
        "--prompt",
        default="Reply with exactly: AI_ADVISOR_OK",
        help="Prompt to send to the advisory AI service.",
    )
    parser.add_argument(
        "--context-file",
        default="",
        help="Optional text file to pass as read-only context.",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=100,
        help="Maximum output tokens for this test call.",
    )
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    context = ""
    if args.context_file:
        context_path = Path(args.context_file)
        if not context_path.exists():
            print(f"[ERROR] Context file not found: {context_path}")
            return 2
        context = context_path.read_text(encoding="utf-8", errors="replace")

    policy = get_ai_safety_policy()
    provider = build_llm_provider(enforce_policy=True)
    provider_info = describe_llm_provider(provider)

    result = ask_ai_advisor(
        args.prompt,
        context=context,
        max_output_tokens=args.max_output_tokens,
        temperature=args.temperature,
    )

    if args.json:
        print(json.dumps(result.to_safe_dict(), indent=2, sort_keys=True))
        return 0 if result.ok else 1

    print("AI Advisor Check")
    print()
    print("Policy")
    print(f"  Effective mode: {policy.effective_mode}")
    print(f"  Can use LLM: {policy.can_use_llm().allowed} -- {policy.can_use_llm().reason}")
    print(f"  Can access broker: {policy.can_access_broker().allowed} -- {policy.can_access_broker().reason}")
    print(f"  Can place order: {policy.can_place_order().allowed} -- {policy.can_place_order().reason}")
    print()
    print("Provider")
    for key, value in provider_info.items():
        print(f"  {key}: {value}")

    print()
    if result.ok:
        print("[OK] Advisory response generated.")
        print(f"Provider: {result.provider}")
        print(f"Model: {result.model}")
        print()
        print(result.content)
        return 0

    if result.blocked:
        print("[BLOCKED] Advisory AI was blocked by configuration.")
    else:
        print("[ERROR] Advisory AI request failed.")

    print(result.reason)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
