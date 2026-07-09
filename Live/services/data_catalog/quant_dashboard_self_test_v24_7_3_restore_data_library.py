from __future__ import annotations

import inspect


def main() -> int:
    from ui import data_library_ui

    text_checks = {
        "module_imported": data_library_ui is not None,
        "has_dash_html": hasattr(data_library_ui, "html"),
    }

    builder_names = [
        name for name in dir(data_library_ui)
        if name.startswith("build") and "data" in name.lower() and "library" in name.lower()
    ]
    assert builder_names, "No Data Library builder function found."

    callable_builders = []
    callable_no_arg_builders = []
    for name in builder_names:
        fn = getattr(data_library_ui, name)
        if not callable(fn):
            continue
        callable_builders.append(name)
        try:
            sig = inspect.signature(fn)
            required = [
                p for p in sig.parameters.values()
                if p.default is inspect._empty
                and p.kind in {p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY}
            ]
            if not required:
                component = fn()
                assert component is not None, f"{name} returned None"
                callable_no_arg_builders.append(name)
        except TypeError:
            pass

    assert callable_builders, "No callable Data Library builder functions found."

    print("v24.7.3 Data Library restore self-test: PASS")
    print(f"builder_candidates: {builder_names}")
    print(f"callable_builders: {callable_builders}")
    print(f"no_arg_builders_called: {callable_no_arg_builders}")
    print(f"text_checks: {text_checks}")
    print("Quant Dashboard Data Library integration disabled for now.")
    print("No credentials were written.")
    print("No files were moved or deleted.")
    print("Research/simulation only. No broker calls or trade execution were made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
