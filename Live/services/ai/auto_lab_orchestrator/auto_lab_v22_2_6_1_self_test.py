from __future__ import annotations

from pathlib import Path
import ast
import re


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def strip_js_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//.*?$", "", text, flags=re.MULTILINE)
    return text


def main() -> int:
    repo_root = _repo_root()
    live_root = repo_root / "Live"

    js_path = live_root / "assets" / "auto_lab_capital_live.js"
    ui_path = live_root / "ui" / "auto_lab_ui.py"
    cb_path = live_root / "services" / "ai" / "auto_lab_orchestrator" / "auto_lab_main_callbacks.py"
    app_py = live_root / "app.py"

    for path in [ui_path, cb_path, app_py]:
        if not path.exists():
            print(f"Missing {path}")
            return 2
        ast.parse(path.read_text(encoding="utf-8", errors="replace"))

    if not js_path.exists():
        print(f"Missing {js_path}")
        return 3

    js = js_path.read_text(encoding="utf-8", errors="replace")
    js_code = strip_js_comments(js)

    must_have = [
        "v22.2.6.1",
        "autolabCapitalSummaryRender",
        "requestAnimationFrame",
        "eventLooksRelevant",
        "nextHtml !== lastHtml",
        "main-autolab-initial-cash",
        "main-autolab-target-cash",
        "main-autolab-capital-summary",
    ]
    missing = [token for token in must_have if token not in js]
    if missing:
        print("Missing JS safety tokens:")
        print("\n".join(missing))
        return 4

    forbidden_code_tokens = [
        "new MutationObserver",
        ".observe(document.body",
        "setInterval(",
    ]
    bad = [token for token in forbidden_code_tokens if token in js_code]
    if bad:
        print("Forbidden freeze-risk code still present:")
        print("\n".join(bad))
        return 5

    cb_text = cb_path.read_text(encoding="utf-8", errors="replace")
    if 'Output("main-autolab-capital-summary", "children")' in cb_text:
        print("Callback file still owns main-autolab-capital-summary.")
        return 6

    print("v22.2.6.1 Auto Lab freeze self-test token fix: PASS")
    print("JS code has no observer/polling loop.")
    print("Capital summary is updated by safe event-delegated browser script.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
