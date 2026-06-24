from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.ai.strategy_language_reference import (
    build_strategy_language_context,
    detect_app_language_violations,
    format_violation_summary,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Strategy AI language reference behavior.")
    parser.add_argument("--prompt", default="Improve this strategy. Return script only.")
    parser.add_argument("--sample-output", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    context = build_strategy_language_context(user_prompt=args.prompt, attached_context="")
    violations = detect_app_language_violations(args.sample_output)

    payload = {
        "prompt": args.prompt,
        "reference_chars": len(context),
        "contains_no_import_rule": "Do not use imports" in context,
        "contains_no_strategy_script_rule": "Do not define strategy_script" in context,
        "violations": [{"label": item.label, "detail": item.detail} for item in violations],
        "violation_summary": format_violation_summary(args.sample_output),
        "reference_preview": context[:1200],
    }

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print("Strategy AI language reference check")
        print(f"Reference chars: {payload['reference_chars']}")
        print(f"No-import rule: {payload['contains_no_import_rule']}")
        print(f"No-strategy_script rule: {payload['contains_no_strategy_script_rule']}")
        print("")
        print(payload["reference_preview"])
        if payload["violation_summary"]:
            print("")
            print(payload["violation_summary"])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
