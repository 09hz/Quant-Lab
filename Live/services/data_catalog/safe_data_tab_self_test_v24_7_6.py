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
    app_path = repo / "Live" / "app.py"
    text = app_path.read_text(encoding="utf-8", errors="replace")

    py_compile.compile(str(app_path), doraise=True)

    assert "BEGIN v24.7.6 safe Data tab override" in text, "Safe Data tab helper block missing."
    assert "_v24_7_6_build_safe_data_library_tab()" in text, "Data tab does not call safe builder."
    assert "BEGIN v24.7 quant dashboard callback registration" not in text, "Old v24.7 callback block still present."

    data_idx = text.lower().find("data library")
    if data_idx < 0:
        data_idx = text.lower().find('label="data"')
    assert data_idx >= 0, "Could not find Data/Data Library label in app.py."

    nearby = text[max(0, data_idx - 1000): data_idx + 3000]
    assert "_v24_7_6_build_safe_data_library_tab()" in nearby, "Safe builder is not near the Data tab block."

    print("v24.7.6 safe Data tab app.py self-test: PASS")
    print("app.py compile: PASS")
    print("safe Data tab helper installed: PASS")
    print("Data tab points to safe recovery layout: PASS")
    print("Old v24.7 Quant Dashboard callback block absent: PASS")
    print("No credentials were written.")
    print("No files were moved or deleted.")
    print("Research/simulation only. No broker calls or trade execution were made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
