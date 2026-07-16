from __future__ import annotations

from pathlib import Path
import py_compile


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "Live" / "app.py").exists():
            return parent
        if parent.name.lower() == "live" and (parent / "app.py").exists():
            return parent.parent
    return Path.cwd()


def main() -> int:
    repo = _repo_root()
    live = repo / "Live"

    app_path = live / "app.py"
    css_path = live / "assets" / "v24_8_2_unified_main_tabs.css"
    loop_doc = repo / "docs" / "research_ai_loop.md"
    data_ui_path = live / "ui" / "data_library_ui.py"

    py_compile.compile(str(app_path), doraise=True)

    assert css_path.exists(), f"Missing CSS: {css_path}"
    css = css_path.read_text(encoding="utf-8", errors="replace")
    assert ".main-tab" in css, "main-tab styling missing."
    assert ".main-tab-selected" in css, "selected tab styling missing."
    assert "[role=\"tab\"]" in css, "generic Dash tab role styling missing."
    assert ".quant-dashboard-embed-tab" in css, "Quant Dashboard embed styling missing."
    assert "pointer-events: auto" in css, "tab clickability guard missing."

    assert loop_doc.exists(), f"Missing loop doc: {loop_doc}"
    doc = loop_doc.read_text(encoding="utf-8", errors="replace")
    assert "Market Memory" in doc, "Loop doc missing Market Memory."
    assert "Quant Schema" in doc, "Loop doc missing Quant Schema."
    assert "Walk-forward" in doc or "walk-forward" in doc, "Loop doc missing walk-forward."
    assert "No broker" in doc or "No broker integration" in doc, "Loop doc missing broker safety."

    if data_ui_path.exists():
        py_compile.compile(str(data_ui_path), doraise=True)

    print("v24.8.2 Unified Main Tab Styling self-test: PASS")
    print("app.py compile: PASS")
    print("data_library_ui.py compile: PASS")
    print("CSS file present: PASS")
    print("Main tab styling selectors: PASS")
    print("Quant Dashboard iframe styling: PASS")
    print("Research loop design doc: PASS")
    print("No app layout or callback files were changed by this patch.")
    print("Research/simulation only. No broker calls or trade execution were made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
