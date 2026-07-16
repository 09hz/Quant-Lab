from __future__ import annotations

from pathlib import Path
import ast


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def main() -> int:
    repo_root = _repo_root()
    live_root = repo_root / "Live"
    cb_path = live_root / "services" / "ai" / "auto_lab_orchestrator" / "auto_lab_main_callbacks.py"
    ui_path = live_root / "ui" / "auto_lab_ui.py"
    app_py = live_root / "app.py"

    for path in [cb_path, ui_path, app_py]:
        if not path.exists():
            print(f"Missing {path}")
            return 2
        if path.suffix == ".py":
            ast.parse(path.read_text(encoding="utf-8", errors="replace"))

    text = cb_path.read_text(encoding="utf-8", errors="replace")

    checks = {
        "has_clientside_callback": "app.clientside_callback" in text,
        "capital_output_once": text.count('Output("main-autolab-capital-summary", "children")') == 1,
        "no_server_refresh_capital_summary": "def refresh_capital_summary" not in text,
        "has_initial_input": 'Input("main-autolab-initial-cash", "value")' in text,
        "has_target_input": 'Input("main-autolab-target-cash", "value")' in text,
        "has_exposure_input": 'Input("main-autolab-cash-exposure", "value")' in text,
        "has_sizing_input": 'Input("main-autolab-sizing-mode", "value")' in text,
        "js_has_money_formatter": "toLocaleString" in text,
        "js_has_dynamic_formula": "target / initial" in text,
    }

    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        print("Failed checks:")
        for name in failed:
            print(f"- {name}: {checks[name]}")
        return 3

    ui_text = ui_path.read_text(encoding="utf-8", errors="replace")
    for cid in [
        "main-autolab-initial-cash",
        "main-autolab-target-cash",
        "main-autolab-cash-exposure",
        "main-autolab-sizing-mode",
        "main-autolab-capital-summary",
    ]:
        if cid not in ui_text:
            print(f"Missing UI id: {cid}")
            return 4

    print("v22.2.4 clientside capital summary self-test: PASS")
    for name, ok in checks.items():
        print(f"{name}: {ok}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
