from __future__ import annotations

from pathlib import Path
import ast


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def main() -> int:
    repo_root = _repo_root()
    live_root = repo_root / "Live"
    ui_path = live_root / "ui" / "auto_lab_ui.py"
    cb_path = live_root / "services" / "ai" / "auto_lab_orchestrator" / "auto_lab_main_callbacks.py"
    js_path = live_root / "assets" / "auto_lab_capital_live.js"
    app_py = live_root / "app.py"

    for path in [ui_path, cb_path, app_py]:
        if not path.exists():
            print(f"Missing {path}")
            return 2
        ast.parse(path.read_text(encoding="utf-8", errors="replace"))

    if not js_path.exists():
        print(f"Missing {js_path}")
        return 3

    ui_text = ui_path.read_text(encoding="utf-8", errors="replace")
    cb_text = cb_path.read_text(encoding="utf-8", errors="replace")
    js_text = js_path.read_text(encoding="utf-8", errors="replace")

    required_ui = [
        "main-autolab-initial-cash",
        "main-autolab-target-cash",
        "main-autolab-cash-exposure",
        "main-autolab-sizing-mode",
        "main-autolab-capital-summary",
        "autolab-capital-summary-html",
    ]
    missing_ui = [x for x in required_ui if x not in ui_text]
    if missing_ui:
        print("Missing UI tokens:")
        print("\n".join(missing_ui))
        return 4

    if 'Output("main-autolab-capital-summary", "children")' in cb_text:
        print("Callback file still outputs to main-autolab-capital-summary; expected DOM fallback only.")
        return 5

    required_js = [
        "main-autolab-initial-cash",
        "main-autolab-target-cash",
        "main-autolab-cash-exposure",
        "main-autolab-capital-summary",
        "autolabCapitalSummaryRender",
        "MutationObserver",
        "setInterval",
    ]
    missing_js = [x for x in required_js if x not in js_text]
    if missing_js:
        print("Missing JS tokens:")
        print("\n".join(missing_js))
        return 6

    print("v22.2.5 DOM capital summary fallback self-test: PASS")
    print("Capital summary is now updated by Live/assets/auto_lab_capital_live.js")
    print("Dash callbacks no longer own main-autolab-capital-summary.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
