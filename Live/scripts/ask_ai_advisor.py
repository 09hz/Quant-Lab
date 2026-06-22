from __future__ import annotations

# --- Local .env loader for IDE/CLI runs ---
# This makes AI advisor scripts behave like Live/app.py when launched from an IDE
# or a fresh terminal that does not already contain the AI/LLM environment vars.
from pathlib import Path as _EnvPath
import sys as _env_sys

_LIVE_DIR = _EnvPath(__file__).resolve().parents[1]
if str(_LIVE_DIR) not in _env_sys.path:
    _env_sys.path.insert(0, str(_LIVE_DIR))

try:
    from services.config.env_loader import load_app_env as _load_app_env

    _load_app_env(override=True, verbose=False)
except Exception as _env_exc:
    print(f"[WARN] Could not load local .env settings: {_env_exc}")
# --- End local .env loader ---

import argparse
from pathlib import Path
import sys

LIVE_ROOT = Path(__file__).resolve().parents[1]
if str(LIVE_ROOT) not in sys.path:
    sys.path.insert(0, str(LIVE_ROOT))

from services.ai.advisor import build_ai_advisor_service  # noqa: E402
from services.ai.prompt_templates import build_prompt, list_template_names  # noqa: E402


HEALTHCHECK_PROMPT = "Reply with exactly: AI_OK"
HEALTHCHECK_SYSTEM_PROMPT = """
You are a minimal connectivity healthcheck responder for a local trading research app.

Rules:
- This is not a trading request.
- Do not discuss broker access, orders, positions, signals, or strategies.
- Do not ask for symbol/timeframe/context.
- Follow the user's exact output instruction.
- If asked to reply with a specific exact string, output only that string.
""".strip()


RAW_SYSTEM_PROMPT = """
You are a read-only assistant inside a trading research app.

Safety rules:
- Do not place, modify, or cancel orders.
- Do not claim broker/account access.
- Do not ask for API keys, passwords, tokens, or secrets.
- For simple connectivity tests, follow exact-output instructions.
""".strip()


def _read_context(context: str, context_file: str) -> str:
    final_context = str(context or "")

    if context_file:
        path = Path(context_file)
        if not path.exists():
            raise FileNotFoundError(f"Context file does not exist: {path}")
        context_from_file = path.read_text(encoding="utf-8", errors="replace")
        final_context = f"{final_context}\n\n{context_from_file}".strip()

    return final_context


def _print_result(result) -> int:
    if not result.ok:
        label = "BLOCKED" if result.blocked else "ERROR"
        print(f"[{label}] {result.reason or 'AI advisor did not return a response.'}")
        return 1

    print(str(result.content or "").strip())
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ask the advisory-only AI service a prompt."
    )
    parser.add_argument(
        "--template",
        default="general",
        choices=list_template_names(),
        help="Prompt template to use for normal advisory mode.",
    )
    parser.add_argument(
        "--prompt",
        default="",
        help="User prompt/question.",
    )
    parser.add_argument(
        "--context",
        default="",
        help="Inline read-only context.",
    )
    parser.add_argument(
        "--context-file",
        default="",
        help="Optional text file containing read-only context.",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=300,
        help="Maximum model output tokens.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.2,
        help="Model temperature.",
    )
    parser.add_argument(
        "--list-templates",
        action="store_true",
        help="List available templates and exit.",
    )
    parser.add_argument(
        "--healthcheck",
        action="store_true",
        help="Run a minimal exact-output LLM healthcheck through AIAdvisorService.",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help=(
            "Bypass advisory prompt templates for simple tests. "
            "Still uses AIAdvisorService and the central AI safety policy."
        ),
    )
    args = parser.parse_args()

    if args.list_templates:
        print("Available advisor templates:")
        for name in list_template_names():
            print(f"  - {name}")
        return 0

    service = build_ai_advisor_service()

    if args.healthcheck:
        print("AI Advisor Healthcheck")
        print("Mode: raw healthcheck")
        print(f"Max output tokens: {min(args.max_output_tokens, 30)}")
        print("")
        result = service.ask(
            HEALTHCHECK_PROMPT,
            context="",
            system_prompt=HEALTHCHECK_SYSTEM_PROMPT,
            max_output_tokens=min(args.max_output_tokens, 30),
            temperature=0.0,
        )
        return _print_result(result)

    try:
        context = _read_context(args.context, args.context_file)
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}")
        return 2

    if not args.prompt and not context:
        print("[ERROR] Provide --prompt, --context, --context-file, or --healthcheck.")
        return 2

    print("AI Advisor")
    print(f"Template: {'raw' if args.raw else args.template}")
    print(f"Max output tokens: {args.max_output_tokens}")
    print("")

    if args.raw:
        result = service.ask(
            args.prompt,
            context=context,
            system_prompt=RAW_SYSTEM_PROMPT,
            max_output_tokens=args.max_output_tokens,
            temperature=args.temperature,
        )
        return _print_result(result)

    prompt, final_context = build_prompt(
        template=args.template,
        user_prompt=args.prompt,
        context=context,
        metadata={"source": "ask_ai_advisor.py"},
    )

    result = service.ask(
        prompt,
        context=final_context,
        max_output_tokens=args.max_output_tokens,
        temperature=args.temperature,
    )
    return _print_result(result)


if __name__ == "__main__":
    raise SystemExit(main())
