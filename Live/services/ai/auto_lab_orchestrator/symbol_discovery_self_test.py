from __future__ import annotations

from pathlib import Path
import ast
import sys


REQUIRED_UI_IDS = {
    "main-autolab-symbols",
    "main-autolab-discovery-theme",
    "main-autolab-discovery-max-symbols",
    "main-autolab-suggest-symbols",
    "main-autolab-discovery-report",
    "main-autolab-discovery-paths",
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
        package_dir / "symbol_discovery.py",
        package_dir / "symbol_discovery_reporter.py",
        package_dir / "auto_lab_main_callbacks.py",
        live_root / "app.py",
    ]
    missing = [str(path) for path in required_files if not path.exists()]
    if missing:
        print("Missing files:")
        print("\n".join(missing))
        return 2

    for path in required_files:
        ast.parse(path.read_text(encoding="utf-8", errors="replace"))

    if str(live_root) not in sys.path:
        sys.path.insert(0, str(live_root))

    from ui.auto_lab_ui import build_auto_lab_tab
    from services.ai.auto_lab_orchestrator.symbol_discovery import discover_symbol_universe
    from services.ai.auto_lab_orchestrator.symbol_discovery_reporter import render_symbol_discovery_markdown, write_symbol_discovery_reports

    layout = build_auto_lab_tab()
    ids: set[str] = set()
    _collect_ids(layout, ids)
    missing_ids = sorted(REQUIRED_UI_IDS - ids)
    if missing_ids:
        print("Missing UI IDs:")
        print("\n".join(missing_ids))
        return 3

    packet = discover_symbol_universe("AMD", "semiconductors, AI infrastructure", 10)
    symbols = packet.get("suggested_symbols", [])
    if "AMD" not in symbols or "NVDA" not in symbols:
        print("Symbol discovery did not include expected AMD/NVDA universe.")
        print(symbols)
        return 4

    md = render_symbol_discovery_markdown(packet)
    if "AI Symbol Discovery Report" not in md or "Suggested universe" not in md:
        print("Markdown render check failed.")
        return 5

    paths = write_symbol_discovery_reports(live_root, packet)
    for key in ["run_dir", "report_path", "json_path", "manifest_path"]:
        if not paths.get(key) or not Path(paths[key]).exists():
            print(f"Missing report artifact: {key}")
            print(paths)
            return 6

    cb_text = (package_dir / "auto_lab_main_callbacks.py").read_text(encoding="utf-8", errors="replace")
    callback_checks = {
        "suggest_symbols_callback": "def suggest_symbols" in cb_text,
        "outputs_symbols_value": 'Output("main-autolab-symbols", "value")' in cb_text,
        "outputs_discovery_report": 'Output("main-autolab-discovery-report", "children")' in cb_text,
        "outputs_discovery_paths": 'Output("main-autolab-discovery-paths", "children")' in cb_text,
        "button_input": 'Input("main-autolab-suggest-symbols", "n_clicks")' in cb_text,
        "no_capital_summary_output": 'Output("main-autolab-capital-summary", "children")' not in cb_text,
    }
    failed = [name for name, ok in callback_checks.items() if not ok]
    if failed:
        print("Callback checks failed:")
        for name in failed:
            print(f"- {name}: {callback_checks[name]}")
        return 7

    print("v22.3 AI Symbol Discovery self-test: PASS")
    print(f"suggested_symbols: {','.join(symbols)}")
    print(f"report_path: {paths['report_path']}")
    for name, ok in callback_checks.items():
        print(f"{name}: {ok}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
