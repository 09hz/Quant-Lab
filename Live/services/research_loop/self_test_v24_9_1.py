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


def _block(text: str) -> str:
    begin = "# BEGIN v24.9.1 research loop controls in quant dashboard"
    end = "# END v24.9.1 research loop controls in quant dashboard"
    start = text.find(begin)
    finish = text.find(end)
    assert start >= 0, "v24.9.1 block start marker missing."
    assert finish >= 0, "v24.9.1 block end marker missing."
    return text[start:finish]


def main() -> int:
    repo = _repo_root()
    live = repo / "Live"
    app_path = live / "app.py"
    css_path = live / "assets" / "v24_9_1_research_loop_controls.css"
    data_ui_path = live / "ui" / "data_library_ui.py"

    py_compile.compile(str(app_path), doraise=True)
    py_compile.compile(str(live / "services" / "research_loop" / "orchestrator.py"), doraise=True)

    text = app_path.read_text(encoding="utf-8", errors="replace")
    block = _block(text)

    assert "research-loop-controls-panel" in block, "Research loop panel missing."
    assert "research-loop-run-button" in block, "Run button missing."
    assert "research-loop-theme" in block, "Theme input missing."
    assert "research-loop-symbols" in block, "Symbols input missing."
    assert "research-loop-max-candidates" in block, "Max candidates input missing."
    assert "research-loop-backend" in block, "Backend selector missing."
    assert "run_research_loop" in block, "Research loop orchestrator callback missing."
    assert "quant-dashboard-native-refresh" in block, "Native dashboard auto-refresh trigger missing."
    assert "simulation_only" in block, "Simulation-only guard missing."
    assert text.count("BEGIN v24.9.1 research loop controls in quant dashboard") == 1, "Duplicate v24.9.1 block."

    assert css_path.exists(), f"Missing CSS: {css_path}"
    css = css_path.read_text(encoding="utf-8", errors="replace")
    assert ".research-loop-controls-panel" in css
    assert ".research-loop-run-button" in css

    if data_ui_path.exists():
        py_compile.compile(str(data_ui_path), doraise=True)
        data_text = data_ui_path.read_text(encoding="utf-8", errors="replace")
        assert "v24.9.1 research loop controls" not in data_text.lower(), "Data Library UI was modified."

    print("v24.9.1 Research Loop Controls self-test: PASS")
    print("app.py compile: PASS")
    print("Research Loop panel IDs: PASS")
    print("Browser callback registration: PASS")
    print("Quant Dashboard auto-refresh trigger: PASS")
    print("CSS present: PASS")
    print("Data Library UI untouched: PASS")
    print("Research/simulation only. No broker calls or trade execution were made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
