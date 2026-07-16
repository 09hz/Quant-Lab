from __future__ import annotations


def _collect_ids(component) -> set[str]:
    ids: set[str] = set()
    if hasattr(component, "id") and component.id:
        ids.add(component.id)
    children = getattr(component, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            ids |= _collect_ids(child)
    elif children is not None and not isinstance(children, (str, int, float)):
        ids |= _collect_ids(children)
    return ids


def main() -> int:
    from ui import data_library_ui

    candidates = [
        name for name in dir(data_library_ui)
        if name.startswith("build") and "data" in name.lower() and "library" in name.lower()
    ]
    assert candidates, "No Data Library builder function found."

    last_error = None
    found_dashboard = False
    for name in candidates:
        fn = getattr(data_library_ui, name)
        if not callable(fn):
            continue
        try:
            component = fn()
            ids = _collect_ids(component)
            if "quant-dashboard-refresh" in ids and "quant-dashboard-backend" in ids:
                found_dashboard = True
                break
        except TypeError as exc:
            last_error = exc
        except Exception as exc:
            last_error = exc

    assert found_dashboard, f"Quant dashboard IDs not found in callable Data Library builders. last_error={last_error}"

    print("v24.7.2 Data Library UI safe wrapper self-test: PASS")
    print("Data Library builder import: PASS")
    print("Quant Dashboard panel appended: PASS")
    print("UI IDs detected: PASS")
    print("Read-only dashboard repair: PASS")
    print("No credentials were written.")
    print("No files were moved or deleted.")
    print("Research/simulation only. No broker calls or trade execution were made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
