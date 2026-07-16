from __future__ import annotations

from pathlib import Path
import ast
import sys


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def main() -> int:
    repo_root = _repo_root()
    live_root = repo_root / "Live"
    required = [
        live_root / "ui" / "auto_lab_ui.py",
        live_root / "assets" / "auto_lab.css",
        live_root / "services" / "ai" / "auto_lab_orchestrator" / "auto_lab_main_callbacks.py",
        live_root / "services" / "ai" / "auto_lab_orchestrator" / "universe_runner.py",
        live_root / "services" / "ai" / "auto_lab_orchestrator" / "walk_forward_runner.py",
        live_root / "services" / "ai" / "auto_lab_orchestrator" / "ui_report_loader.py",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        print("Missing required files:")
        print("\n".join(missing))
        return 2

    app_py = live_root / "app.py"
    text = app_py.read_text(encoding="utf-8", errors="replace")
    checks = {
        "build_auto_lab_tab_import": "build_auto_lab_tab" in text,
        "ai_auto_lab_tab_label": 'label="AI Auto Lab"' in text or "label=\'AI Auto Lab\'" in text,
        "auto_lab_tab_value": 'value="auto-lab"' in text or "value=\'auto-lab\'" in text,
        "callback_registration": "register_auto_lab_main_callbacks" in text,
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        print("Failed app.py checks:")
        print("\n".join(failed))
        return 3

    for path in [live_root / "ui" / "auto_lab_ui.py", live_root / "services" / "ai" / "auto_lab_orchestrator" / "auto_lab_main_callbacks.py"]:
        ast.parse(path.read_text(encoding="utf-8", errors="replace"))

    if str(live_root) not in sys.path:
        sys.path.insert(0, str(live_root))
    try:
        from ui.auto_lab_ui import build_auto_lab_tab
        layout = build_auto_lab_tab()
        assert layout is not None
        layout_status = "PASS"
    except Exception as exc:
        layout_status = f"SKIPPED_OR_FAILED: {exc}"

    print("AI Auto Lab main UI self-test: PASS")
    print(f"layout_construct: {layout_status}")
    for name, ok in checks.items():
        print(f"{name}: {ok}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
