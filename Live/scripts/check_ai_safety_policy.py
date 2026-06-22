from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


LIVE_ROOT = Path(__file__).resolve().parents[1]
if str(LIVE_ROOT) not in sys.path:
    sys.path.insert(0, str(LIVE_ROOT))

from services.safety.ai_policy import get_ai_safety_policy  # noqa: E402


def _decision_to_dict(decision) -> dict:
    return {
        "allowed": bool(decision.allowed),
        "reason": decision.reason,
        "required_human_confirmation": bool(decision.required_human_confirmation),
        "metadata": decision.metadata or {},
    }


def _print_text_report(strict: bool = False) -> int:
    policy = get_ai_safety_policy()
    data = policy.to_safe_dict()
    issues = data.get("violations", [])

    print("AI Safety Policy Check")
    print(f"Effective mode: {data['effective_mode']}")
    print("")
    print("Locks:")
    print(f"  AI_FEATURES_ENABLED: {policy.ai_features_enabled}")
    print(f"  AI_ADVISORY_ONLY: {policy.ai_advisory_only}")
    print(f"  AI_ALLOW_ORDER_PLACEMENT: {policy.ai_allow_order_placement}")
    print(f"  AI_ALLOW_BROKER_ACCESS: {policy.ai_allow_broker_access}")
    print(f"  AI_ALLOW_EXTERNAL_TOOLS: {policy.ai_allow_external_tools}")
    print(f"  AI_REQUIRE_HUMAN_CONFIRMATION: {policy.ai_require_human_confirmation}")
    print("")
    print("LLM:")
    print(f"  LLM_PROVIDER: {policy.llm_provider}")
    print(f"  LLM_BASE_URL configured: {policy.llm_base_url_configured}")
    print(f"  OPENAI_API_KEY configured: {policy.openai_api_key_configured}")
    print("")

    llm_decision = policy.can_use_llm()
    broker_decision = policy.can_access_broker()
    order_decision = policy.can_place_order()

    print("Decisions:")
    print(f"  Can use LLM: {llm_decision.allowed} -- {llm_decision.reason}")
    print(f"  Can access broker: {broker_decision.allowed} -- {broker_decision.reason}")
    print(f"  Can place order: {order_decision.allowed} -- {order_decision.reason}")

    if issues:
        print("")
        print("Configuration issues:")
        for issue in issues:
            print(f"  - {issue}")

    if strict and issues:
        return 2

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Check AI safety policy locks.")
    parser.add_argument("--json", action="store_true", help="Print safe JSON output.")
    parser.add_argument("--strict", action="store_true", help="Return non-zero if configuration issues exist.")
    args = parser.parse_args()

    policy = get_ai_safety_policy()

    if args.json:
        data = policy.to_safe_dict()
        data["decisions"] = {
            "can_use_llm": _decision_to_dict(policy.can_use_llm()),
            "can_access_broker": _decision_to_dict(policy.can_access_broker()),
            "can_place_order": _decision_to_dict(policy.can_place_order()),
        }
        print(json.dumps(data, indent=2, sort_keys=True))
        if args.strict and data.get("violations"):
            return 2
        return 0

    return _print_text_report(strict=args.strict)


if __name__ == "__main__":
    raise SystemExit(main())
