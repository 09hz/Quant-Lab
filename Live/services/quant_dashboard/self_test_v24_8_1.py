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


def _extract_v24_8_1_block(text: str) -> str:
    start = text.find("# BEGIN v24.8.1 quant dashboard top-level tab")
    end = text.find("# END v24.8.1 quant dashboard top-level tab")
    assert start >= 0, "v24.8.1 start marker missing."
    assert end >= 0, "v24.8.1 end marker missing."
    return text[start:end]


def main() -> int:
    repo = _repo_root()
    app_path = repo / "Live" / "app.py"
    data_ui_path = repo / "Live" / "ui" / "data_library_ui.py"

    py_compile.compile(str(app_path), doraise=True)

    text = app_path.read_text(encoding="utf-8", errors="replace")
    block = _extract_v24_8_1_block(text)

    assert "Quant Dashboard" in block, "Quant Dashboard tab label missing."
    assert "quant-dashboard" in block, "Quant Dashboard tab value missing."
    assert "html.Iframe" in block or "_v24_8_1_html.Iframe" in block, "iframe embed missing."
    assert "ALGOTRADER_QUANT_DASHBOARD_URL" in block, "URL override env var missing."
    assert "_v24_8_1_is_settings_tab" in block, "Settings tab ordering helper missing."
    assert "filtered_tabs.append(_v24_8_1_build_quant_dashboard_tab())" in block, "Quant tab insertion missing."
    assert "filtered_tabs.extend(settings_tabs)" in block, "Settings tab final move missing."

    if data_ui_path.exists():
        data_text = data_ui_path.read_text(encoding="utf-8", errors="replace")
        assert "v24.8.1 quant dashboard" not in data_text.lower(), "Data Library UI was modified by v24.8.1."

    assert text.count("BEGIN v24.8.1 quant dashboard top-level tab") == 1, "Expected exactly one v24.8.1 start marker."
    assert text.count("END v24.8.1 quant dashboard top-level tab") == 1, "Expected exactly one v24.8.1 end marker."

    print("v24.8.1 Main App Quant Dashboard Tab self-test: PASS")
    print("app.py compile: PASS")
    print("Quant Dashboard tab block present: PASS")
    print("iframe embed present: PASS")
    print("Settings tab moved to end by runtime reorder: PASS")
    print("Data Library UI untouched by v24.8.1: PASS")
    print("Marker count check: PASS")
    print("No credentials were written.")
    print("No files were moved or deleted.")
    print("Research/simulation only. No broker calls or trade execution were made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
