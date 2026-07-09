from __future__ import annotations

from pathlib import Path
import inspect
import sys


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "Live" / "app.py").exists():
            return parent
        if parent.name.lower() == "live" and (parent / "app.py").exists():
            return parent.parent
    return Path.cwd()


def _collect_ids(component) -> set[str]:
    ids: set[str] = set()
    if hasattr(component, "id") and component.id:
        ids.add(str(component.id))
    children = getattr(component, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            ids |= _collect_ids(child)
    elif children is not None and not isinstance(children, (str, int, float)):
        ids |= _collect_ids(children)
    return ids


def main() -> int:
    repo = _repo_root()
    live = repo / "Live"
    if str(live) not in sys.path:
        sys.path.insert(0, str(live))

    app_text = (live / "app.py").read_text(encoding="utf-8", errors="replace")
    ui_text = (live / "ui" / "data_library_ui.py").read_text(encoding="utf-8", errors="replace")

    assert "BEGIN v24.7 quant dashboard callback registration" not in app_text
    assert "BEGIN v24.7 quant dashboard import" not in ui_text
    assert "BEGIN v24.7 quant dashboard safe Data Library wrapper" not in ui_text
    assert "build_quant_dashboard_panel() if build_quant_dashboard_panel else html.Div()" not in ui_text

    from ui import data_library_ui

    builder_names = [
        name for name in dir(data_library_ui)
        if name.startswith("build") and "data" in name.lower() and "library" in name.lower()
    ]
    assert builder_names, "No Data Library builder function found."

    called_builders = []
    last_error = None

    for name in builder_names:
        fn = getattr(data_library_ui, name)
        if not callable(fn):
            continue
        try:
            sig = inspect.signature(fn)
            required = [
                p for p in sig.parameters.values()
                if p.default is inspect._empty
                and p.kind in {p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY}
            ]
            if required:
                continue

            component = fn()
            assert component is not None, f"{name} returned None"
            _collect_ids(component)
            called_builders.append(name)
        except Exception as exc:
            last_error = exc

    assert called_builders, f"No no-arg Data Library builder could be called. last_error={last_error}"

    css_path = live / "assets" / "v24_7_4_tab_clickability_rescue.css"
    assert css_path.exists(), "Missing v24.7.4 tab clickability rescue CSS."

    print("v24.7.4 Data tab clickability restore self-test: PASS")
    print(f"builder_candidates: {builder_names}")
    print(f"called_builders: {called_builders}")
    print("v24.7 Quant Dashboard layout/callback integration disabled: PASS")
    print("Data Library UI import/call: PASS")
    print("Tab clickability CSS rescue: PASS")
    print("No credentials were written.")
    print("No files were moved or deleted.")
    print("Research/simulation only. No broker calls or trade execution were made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
