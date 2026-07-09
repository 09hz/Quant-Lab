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


def _extract_block(text: str) -> str:
    begin = "# BEGIN v24.8.3 native quant dashboard tab"
    end = "# END v24.8.3 native quant dashboard tab"
    start = text.find(begin)
    finish = text.find(end)
    assert start >= 0, "v24.8.3 native block start marker missing."
    assert finish >= 0, "v24.8.3 native block end marker missing."
    return text[start:finish]


def main() -> int:
    repo = _repo_root()
    live = repo / "Live"
    app_path = live / "app.py"
    css_path = live / "assets" / "v24_8_3_native_quant_dashboard.css"
    data_ui_path = live / "ui" / "data_library_ui.py"

    py_compile.compile(str(app_path), doraise=True)
    py_compile.compile(str(live / "services" / "quant_dashboard" / "queries.py"), doraise=True)

    text = app_path.read_text(encoding="utf-8", errors="replace")
    block = _extract_block(text)

    assert "Quant Dashboard" in block, "Quant Dashboard label missing."
    assert "quant-dashboard" in block, "Quant Dashboard value missing."
    assert "Iframe" not in block, "Native tab must not use iframe."
    assert "127.0.0.1:8061" not in block, "Native tab must not require standalone port 8061."
    assert "load_quant_dashboard" in block, "Native tab must call quant dashboard query service."
    assert "quant-dashboard-native-refresh" in block, "Native refresh button missing."
    assert "quant-dashboard-native-backend" in block, "Native backend selector missing."
    assert "filtered_tabs.extend(settings_tabs)" in block, "Settings tab move-to-end behavior missing."
    assert text.count("BEGIN v24.8.3 native quant dashboard tab") == 1, "Expected exactly one v24.8.3 block."
    assert "BEGIN v24.8.1 quant dashboard top-level tab" not in text, "Old iframe integration block still present."

    assert css_path.exists(), f"Missing CSS file: {css_path}"
    css = css_path.read_text(encoding="utf-8", errors="replace")
    assert ".quant-native-page" in css, "Native Quant CSS page class missing."
    assert ".quant-native-controls" in css, "Native Quant CSS controls class missing."

    if data_ui_path.exists():
        py_compile.compile(str(data_ui_path), doraise=True)
        data_text = data_ui_path.read_text(encoding="utf-8", errors="replace")
        assert "v24.8.3 native quant dashboard" not in data_text.lower(), "Data Library UI was modified."

    print("v24.8.3 Native Quant Dashboard Tab self-test: PASS")
    print("app.py compile: PASS")
    print("Native Quant tab block present: PASS")
    print("No iframe / no port 8061 requirement: PASS")
    print("Quant query service callback present: PASS")
    print("Settings tab moved to end by runtime reorder: PASS")
    print("Data Library UI untouched: PASS")
    print("CSS present: PASS")
    print("Research/simulation only. No broker calls or trade execution were made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
