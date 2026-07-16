from __future__ import annotations

from pathlib import Path
import ast
import sys


REQUIRED_IDS = {
    "main-autolab-initial-cash",
    "main-autolab-target-cash",
    "main-autolab-capital-summary",
    "main-autolab-universe-script",
    "main-autolab-walk-forward-script",
    "main-autolab-script-paths",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _collect_ids(component, out: set[str]) -> None:
    component_id = getattr(component, "id", None)
    if isinstance(component_id, str):
        out.add(component_id)
    children = getattr(component, "children", None)
    if children is None:
        return
    if isinstance(children, (list, tuple)):
        for child in children:
            _collect_ids(child, out)
    else:
        _collect_ids(children, out)


def main() -> int:
    repo_root = _repo_root()
    live_root = repo_root / "Live"
    package_dir = live_root / "services" / "ai" / "auto_lab_orchestrator"

    required_files = [
        live_root / "ui" / "auto_lab_ui.py",
        live_root / "assets" / "auto_lab.css",
        package_dir / "auto_lab_main_callbacks.py",
        package_dir / "capital_controls.py",
        package_dir / "script_viewer.py",
        package_dir / "universe_runner.py",
        package_dir / "walk_forward_runner.py",
        package_dir / "ui_report_loader.py",
    ]
    missing = [str(path) for path in required_files if not path.exists()]
    if missing:
        print("Missing required files:")
        print("\n".join(missing))
        return 2

    for path in required_files:
        if path.suffix == ".py":
            ast.parse(path.read_text(encoding="utf-8", errors="replace"))

    app_py = live_root / "app.py"
    app_text = app_py.read_text(encoding="utf-8", errors="replace")
    app_checks = {
        "app_imports_build_auto_lab_tab": "build_auto_lab_tab" in app_text,
        "app_has_ai_auto_lab_tab": 'label="AI Auto Lab"' in app_text or "label='AI Auto Lab'" in app_text,
        "app_registers_callbacks": "register_auto_lab_main_callbacks" in app_text,
    }
    failed_app = [name for name, ok in app_checks.items() if not ok]
    if failed_app:
        print("Failed app.py checks:")
        print("\n".join(failed_app))
        return 3

    if str(live_root) not in sys.path:
        sys.path.insert(0, str(live_root))

    from ui.auto_lab_ui import build_auto_lab_tab
    from services.ai.auto_lab_orchestrator.capital_controls import normalize_capital, capital_markdown
    from services.ai.auto_lab_orchestrator.script_viewer import build_script_packet

    layout = build_auto_lab_tab()
    ids: set[str] = set()
    _collect_ids(layout, ids)
    missing_ids = sorted(REQUIRED_IDS - ids)
    if missing_ids:
        print("Missing layout IDs:")
        print("\n".join(missing_ids))
        return 4

    capital = normalize_capital(12000, 24000, 95, "percent_cash_exposure")
    md = capital_markdown(capital)
    if "Starting cash" not in md or "Target cash" not in md:
        print("Capital markdown check failed.")
        return 5

    packet = build_script_packet(live_root)
    if "paths" not in packet:
        print("Script packet check failed.")
        return 6

    print("v22.2 Auto Lab capital controls + script viewer self-test: PASS")
    print(f"layout_ids_checked: {len(REQUIRED_IDS)}")
    for name, ok in app_checks.items():
        print(f"{name}: {ok}")
    print(f"capital_target_return_pct: {capital.target_return_pct:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
