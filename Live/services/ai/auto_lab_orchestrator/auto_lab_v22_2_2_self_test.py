from __future__ import annotations

from pathlib import Path
import ast
import re
import sys


REQUIRED_LAYOUT_IDS = {
    "main-autolab-initial-cash",
    "main-autolab-target-cash",
    "main-autolab-cash-exposure",
    "main-autolab-sizing-mode",
    "main-autolab-capital-summary",
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

    ui_path = live_root / "ui" / "auto_lab_ui.py"
    cb_path = package_dir / "auto_lab_main_callbacks.py"
    cap_path = package_dir / "capital_controls.py"

    for path in [ui_path, cb_path, cap_path]:
        if not path.exists():
            print(f"Missing {path}")
            return 2
        ast.parse(path.read_text(encoding="utf-8", errors="replace"))

    cb_text = cb_path.read_text(encoding="utf-8", errors="replace")

    capital_output_count = cb_text.count('Output("main-autolab-capital-summary", "children")')
    if capital_output_count != 1:
        print(f"Expected exactly one capital summary Output, found {capital_output_count}")
        return 3

    capital_callback_match = re.search(
        r'Output\("main-autolab-capital-summary", "children"\).*?def refresh_capital_summary',
        cb_text,
        flags=re.DOTALL,
    )
    if not capital_callback_match:
        print("Dedicated refresh_capital_summary callback not found.")
        return 4

    required_inputs = [
        'Input("main-autolab-initial-cash", "value")',
        'Input("main-autolab-target-cash", "value")',
        'Input("main-autolab-cash-exposure", "value")',
        'Input("main-autolab-sizing-mode", "value")',
    ]
    missing_inputs = [item for item in required_inputs if item not in cb_text]
    if missing_inputs:
        print("Missing dedicated capital callback inputs:")
        print("\n".join(missing_inputs))
        return 5

    if str(live_root) not in sys.path:
        sys.path.insert(0, str(live_root))
    from ui.auto_lab_ui import build_auto_lab_tab
    from services.ai.auto_lab_orchestrator.capital_controls import normalize_capital, capital_markdown

    layout = build_auto_lab_tab()
    ids: set[str] = set()
    _collect_ids(layout, ids)
    missing_ids = sorted(REQUIRED_LAYOUT_IDS - ids)
    if missing_ids:
        print("Missing layout IDs:")
        print("\n".join(missing_ids))
        return 6

    cap = normalize_capital(15000, 30000, 80, "percent_cash_exposure")
    md = capital_markdown(cap)
    if "$15,000.00" not in md or "$30,000.00" not in md or "80.00%" not in md:
        print("Capital markdown dynamic value check failed.")
        print(md)
        return 7

    print("v22.2.2 split live capital callback self-test: PASS")
    print("Capital summary now has a dedicated callback.")
    print("Capital markdown dynamic check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
