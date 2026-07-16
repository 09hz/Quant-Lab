from __future__ import annotations

from pathlib import Path
import ast
import re


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def main() -> int:
    repo_root = _repo_root()
    live_root = repo_root / "Live"
    callback_path = live_root / "services" / "ai" / "auto_lab_orchestrator" / "auto_lab_main_callbacks.py"

    if not callback_path.exists():
        print(f"Missing {callback_path}")
        return 2

    text = callback_path.read_text(encoding="utf-8", errors="replace")
    ast.parse(text)

    required_inputs = [
        'Input("main-autolab-initial-cash", "value")',
        'Input("main-autolab-target-cash", "value")',
        'Input("main-autolab-cash-exposure", "value")',
        'Input("main-autolab-sizing-mode", "value")',
    ]

    missing = [item for item in required_inputs if item not in text]
    if missing:
        print("Capital fields are not live Inputs:")
        print("\n".join(missing))
        return 3

    forbidden_state = [
        'State("main-autolab-initial-cash", "value")',
        'State("main-autolab-target-cash", "value")',
        'State("main-autolab-cash-exposure", "value")',
        'State("main-autolab-sizing-mode", "value")',
    ]
    bad = [item for item in forbidden_state if item in text]
    if bad:
        print("Capital fields still appear as State:")
        print("\n".join(bad))
        return 4

    app_py = live_root / "app.py"
    if app_py.exists():
        ast.parse(app_py.read_text(encoding="utf-8", errors="replace"))

    print("v22.2.1 live capital summary refresh self-test: PASS")
    print("Capital fields now trigger callback updates as Inputs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
