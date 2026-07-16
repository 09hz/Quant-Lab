#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import contextlib
import importlib.util
import inspect
import io
import json
import os
import re
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CHANGELOG = """# diagnose_auto_lab_capital_callback_v22_2_3

## Purpose

Read-only diagnostic for the AI Auto Lab capital summary panel.

This verifies:

- The capital input component IDs exist in the layout.
- `capital_controls.normalize_capital()` and `capital_markdown()` produce dynamic values.
- `auto_lab_main_callbacks.py` defines/registers a dedicated capital summary callback.
- `Live/app.py` imports/builds the AI Auto Lab tab.
- `Live/app.py` registers `register_auto_lab_main_callbacks(app)`.
- The imported Dash app callback map contains `main-autolab-capital-summary.children`.
- The callback inputs are the expected capital fields.
- Whether there are duplicate/missing output registrations.

## Safety

Read-only diagnostic for code/runtime inspection.

No backups.
No app patching.
No broker calls.
No live orders.
No PaperBroker calls.
"""


CAPITAL_IDS = [
    "main-autolab-initial-cash",
    "main-autolab-target-cash",
    "main-autolab-cash-exposure",
    "main-autolab-sizing-mode",
]

EXPECTED_CAPITAL_OUTPUT = "main-autolab-capital-summary.children"


def find_repo_root(start: Path) -> Path:
    start = start.resolve()
    for candidate in [start, *start.parents]:
        if (candidate / "Live" / "app.py").exists() and (candidate / "Live" / "services").is_dir():
            return candidate
        if (candidate / "app.py").exists() and candidate.name.lower() == "live":
            return candidate.parent
    raise SystemExit("Could not locate repo root containing Live/app.py")


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except Exception:
        return str(path)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def collect_ids(component: Any, out: set[str]) -> None:
    component_id = getattr(component, "id", None)
    if isinstance(component_id, str):
        out.add(component_id)

    children = getattr(component, "children", None)
    if children is None:
        return

    if isinstance(children, (list, tuple)):
        for child in children:
            collect_ids(child, out)
    else:
        collect_ids(children, out)


def component_prop(component: Any, component_id: str, prop: str) -> Any:
    found = []

    def walk(node: Any) -> None:
        node_id = getattr(node, "id", None)
        if node_id == component_id:
            found.append(getattr(node, prop, None))
        children = getattr(node, "children", None)
        if children is None:
            return
        if isinstance(children, (list, tuple)):
            for child in children:
                walk(child)
        else:
            walk(children)

    walk(component)
    return found[0] if found else None


def static_checks(repo_root: Path) -> dict[str, Any]:
    live_root = repo_root / "Live"
    app_py = live_root / "app.py"
    ui_py = live_root / "ui" / "auto_lab_ui.py"
    cb_py = live_root / "services" / "ai" / "auto_lab_orchestrator" / "auto_lab_main_callbacks.py"
    cap_py = live_root / "services" / "ai" / "auto_lab_orchestrator" / "capital_controls.py"

    files = {
        "app_py": app_py,
        "auto_lab_ui_py": ui_py,
        "auto_lab_main_callbacks_py": cb_py,
        "capital_controls_py": cap_py,
    }

    data: dict[str, Any] = {
        "files": {
            name: {
                "path": rel(path, repo_root),
                "exists": path.exists(),
                "size": path.stat().st_size if path.exists() else None,
            }
            for name, path in files.items()
        },
        "syntax": {},
        "app_static": {},
        "callback_static": {},
        "ui_static": {},
    }

    for name, path in files.items():
        if path.exists() and path.suffix == ".py":
            try:
                ast.parse(read_text(path))
                data["syntax"][name] = "PASS"
            except Exception as exc:
                data["syntax"][name] = f"FAIL: {exc}"

    app_text = read_text(app_py)
    cb_text = read_text(cb_py)
    ui_text = read_text(ui_py)

    data["app_static"] = {
        "has_ai_auto_lab_label": 'label="AI Auto Lab"' in app_text or "label='AI Auto Lab'" in app_text,
        "has_auto_lab_value": 'value="auto-lab"' in app_text or "value='auto-lab'" in app_text,
        "imports_build_auto_lab_tab": "build_auto_lab_tab" in app_text,
        "calls_build_auto_lab_tab": "build_auto_lab_tab()" in app_text,
        "registers_auto_lab_main_callbacks": "register_auto_lab_main_callbacks(app)" in app_text,
        "register_auto_lab_main_callbacks_mentions": app_text.count("register_auto_lab_main_callbacks"),
        "capital_summary_mentions": app_text.count("main-autolab-capital-summary"),
    }

    output_pattern = r'Output\(\s*["\']main-autolab-capital-summary["\']\s*,\s*["\']children["\']\s*\)'
    data["callback_static"] = {
        "defines_register_method": "def register_auto_lab_main_callbacks" in cb_text,
        "defines_refresh_capital_summary": "def refresh_capital_summary" in cb_text,
        "capital_summary_output_count": len(re.findall(output_pattern, cb_text)),
        "capital_input_mentions": {
            cid: cb_text.count(cid)
            for cid in CAPITAL_IDS
        },
        "capital_output_mentions": cb_text.count("main-autolab-capital-summary"),
        "large_callback_outputs_capital_summary": bool(
            re.search(
                r'Output\(\s*["\']main-autolab-command-output["\'].*?Output\(\s*["\']main-autolab-capital-summary["\']',
                cb_text,
                flags=re.DOTALL,
            )
        ),
        "capital_inputs_as_input": {
            cid: f'Input("{cid}", "value")' in cb_text or f"Input('{cid}', 'value')" in cb_text
            for cid in CAPITAL_IDS
        },
        "capital_inputs_as_state": {
            cid: f'State("{cid}", "value")' in cb_text or f"State('{cid}', 'value')" in cb_text
            for cid in CAPITAL_IDS
        },
    }

    data["ui_static"] = {
        "layout_has_capital_summary_id": "main-autolab-capital-summary" in ui_text,
        "layout_capital_ids": {cid: cid in ui_text for cid in CAPITAL_IDS},
        "number_inputs_debounce_false_count": ui_text.count("debounce=False"),
    }

    return data


def import_auto_lab_layout(repo_root: Path) -> dict[str, Any]:
    live_root = repo_root / "Live"
    result: dict[str, Any] = {
        "ok": False,
        "ids": [],
        "missing_ids": [],
        "component_props": {},
        "error": "",
        "traceback": "",
    }

    sys.path.insert(0, str(live_root))
    sys.path.insert(0, str(repo_root))

    try:
        from ui.auto_lab_ui import build_auto_lab_tab

        layout = build_auto_lab_tab()
        ids: set[str] = set()
        collect_ids(layout, ids)

        result["ok"] = True
        result["ids"] = sorted(ids)
        result["missing_ids"] = sorted(set([*CAPITAL_IDS, "main-autolab-capital-summary"]) - ids)
        result["component_props"] = {
            cid: {
                "value": component_prop(layout, cid, "value"),
                "debounce": component_prop(layout, cid, "debounce"),
                "type": str(type(component_prop(layout, cid, "value")).__name__),
            }
            for cid in CAPITAL_IDS
        }
    except Exception as exc:
        result["error"] = str(exc)
        result["traceback"] = traceback.format_exc()

    return result


def import_capital_methods(repo_root: Path) -> dict[str, Any]:
    live_root = repo_root / "Live"
    result: dict[str, Any] = {
        "ok": False,
        "sample": {},
        "dynamic_markdown_contains_sample_values": False,
        "error": "",
        "traceback": "",
    }

    sys.path.insert(0, str(live_root))
    sys.path.insert(0, str(repo_root))

    try:
        from services.ai.auto_lab_orchestrator.capital_controls import (
            capital_markdown,
            normalize_capital,
        )

        capital = normalize_capital(
            initial_cash=15000,
            target_cash=30000,
            cash_exposure_pct=80,
            sizing_mode="percent_cash_exposure",
        )
        markdown = capital_markdown(capital)
        result["ok"] = True
        result["sample"] = {
            "capital_dict": capital.to_dict(),
            "markdown": markdown,
        }
        result["dynamic_markdown_contains_sample_values"] = all(
            token in markdown
            for token in ["$15,000.00", "$30,000.00", "80.00%", "100.00%"]
        )
    except Exception as exc:
        result["error"] = str(exc)
        result["traceback"] = traceback.format_exc()

    return result


def import_app_and_check_callback_map(repo_root: Path) -> dict[str, Any]:
    live_root = repo_root / "Live"
    app_py = live_root / "app.py"

    result: dict[str, Any] = {
        "ok": False,
        "import_stdout": "",
        "import_stderr": "",
        "import_error": "",
        "import_traceback": "",
        "app_object_found": False,
        "callback_count": None,
        "capital_callback_keys": [],
        "capital_callback": {},
        "capital_callback_inputs": [],
        "capital_callback_states": [],
        "capital_callback_function": "",
        "capital_callback_direct_call": {},
        "app_layout_ids": [],
        "app_layout_missing_ids": [],
    }

    old_cwd = Path.cwd()
    old_sys_path = list(sys.path)
    stdout = io.StringIO()
    stderr = io.StringIO()

    try:
        os.chdir(live_root)
        sys.path.insert(0, str(live_root))
        sys.path.insert(0, str(repo_root))

        spec = importlib.util.spec_from_file_location("autolab_diagnostic_app_import", app_py)
        if spec is None or spec.loader is None:
            raise RuntimeError("Could not create import spec for Live/app.py")

        module = importlib.util.module_from_spec(spec)

        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            spec.loader.exec_module(module)

        result["ok"] = True
        app = getattr(module, "app", None)
        result["app_object_found"] = app is not None

        if app is not None:
            callback_map = getattr(app, "callback_map", {}) or {}
            result["callback_count"] = len(callback_map)
            capital_keys = [key for key in callback_map.keys() if "main-autolab-capital-summary" in key]
            result["capital_callback_keys"] = capital_keys

            if capital_keys:
                key = capital_keys[0]
                cb = callback_map.get(key, {})
                result["capital_callback"] = {
                    k: str(v)
                    for k, v in cb.items()
                    if k not in {"callback"}
                }
                inputs = cb.get("inputs", []) or []
                states = cb.get("state", []) or []
                result["capital_callback_inputs"] = inputs
                result["capital_callback_states"] = states

                func = cb.get("callback")
                if func is not None:
                    result["capital_callback_function"] = getattr(func, "__name__", repr(func))
                    original = getattr(func, "__wrapped__", None)
                    candidate = original or func
                    try:
                        sig = inspect.signature(candidate)
                        result["capital_callback_direct_call"]["signature"] = str(sig)
                        if len(sig.parameters) == 4:
                            direct = candidate(15000, 30000, 80, "percent_cash_exposure")
                            result["capital_callback_direct_call"]["ok"] = True
                            result["capital_callback_direct_call"]["result"] = str(direct)
                            result["capital_callback_direct_call"]["contains_sample_values"] = all(
                                token in str(direct)
                                for token in ["$15,000.00", "$30,000.00", "80.00%"]
                            )
                        else:
                            result["capital_callback_direct_call"]["ok"] = False
                            result["capital_callback_direct_call"]["reason"] = "callback signature is not four plain parameters"
                    except Exception as exc:
                        result["capital_callback_direct_call"]["ok"] = False
                        result["capital_callback_direct_call"]["error"] = str(exc)
                        result["capital_callback_direct_call"]["traceback"] = traceback.format_exc()

            try:
                app_ids: set[str] = set()
                collect_ids(getattr(app, "layout", None), app_ids)
                result["app_layout_ids"] = sorted(app_ids)
                result["app_layout_missing_ids"] = sorted(
                    set([*CAPITAL_IDS, "main-autolab-capital-summary"]) - app_ids
                )
            except Exception as exc:
                result["app_layout_ids_error"] = str(exc)

    except Exception as exc:
        result["import_error"] = str(exc)
        result["import_traceback"] = traceback.format_exc()
    finally:
        result["import_stdout"] = stdout.getvalue()
        result["import_stderr"] = stderr.getvalue()
        os.chdir(old_cwd)
        sys.path[:] = old_sys_path

    return result


def make_recommendations(diag: dict[str, Any]) -> list[str]:
    recs: list[str] = []

    static = diag.get("static", {})
    cb_static = static.get("callback_static", {})
    app_static = static.get("app_static", {})
    layout = diag.get("layout_import", {})
    cap = diag.get("capital_methods", {})
    app_runtime = diag.get("app_runtime", {})

    if not app_static.get("registers_auto_lab_main_callbacks"):
        recs.append("BLOCKER: Live/app.py does not call register_auto_lab_main_callbacks(app).")
    if not app_static.get("calls_build_auto_lab_tab"):
        recs.append("BLOCKER: Live/app.py does not call build_auto_lab_tab().")
    if cb_static.get("capital_summary_output_count") != 1:
        recs.append(
            f"BLOCKER: expected exactly one capital summary Output in auto_lab_main_callbacks.py, found {cb_static.get('capital_summary_output_count')}."
        )
    if cb_static.get("large_callback_outputs_capital_summary"):
        recs.append("BLOCKER: capital summary still appears inside the large report callback outputs.")
    if layout.get("missing_ids"):
        recs.append(f"BLOCKER: Auto Lab layout missing IDs: {layout.get('missing_ids')}.")
    if not cap.get("dynamic_markdown_contains_sample_values"):
        recs.append("BLOCKER: capital_markdown() did not render sample changed values.")
    if app_runtime.get("import_error"):
        recs.append("BLOCKER: importing Live/app.py failed; callback map could not be verified.")
    elif not app_runtime.get("app_object_found"):
        recs.append("BLOCKER: imported Live/app.py but no `app` object was found.")
    elif not app_runtime.get("capital_callback_keys"):
        recs.append("BLOCKER: Dash callback_map does not contain main-autolab-capital-summary.children.")
    else:
        input_ids = sorted((item.get("id") for item in app_runtime.get("capital_callback_inputs", []) if isinstance(item, dict)))
        missing_inputs = sorted(set(CAPITAL_IDS) - set(input_ids))
        if missing_inputs:
            recs.append(f"BLOCKER: capital callback is missing expected Inputs: {missing_inputs}.")
        if app_runtime.get("capital_callback_states"):
            recs.append("WARNING: capital callback has State entries; it should be Inputs-only for live refresh.")

    if not recs:
        recs.append(
            "Static and runtime checks look correct. If the browser still shows old values, likely causes are: app not fully restarted, browser cache/stale page, duplicate server still running on the same/old port, or the visible component is from a different layout instance."
        )
        recs.append(
            "Recommended next action: stop all python app processes, restart app.py, hard-refresh browser with Ctrl+F5, then test again."
        )

    return recs


def render_markdown(diag: dict[str, Any]) -> str:
    lines = [
        "# v22.2.3 Auto Lab Capital Callback Diagnostic",
        "",
        f"- generated_at: `{diag.get('generated_at')}`",
        f"- repo_root: `{diag.get('repo_root')}`",
        "",
        "## Verdict / Recommendations",
        "",
    ]

    for rec in diag.get("recommendations", []):
        lines.append(f"- {rec}")

    lines.extend(["", "## Static checks", ""])
    lines.append("```json")
    lines.append(json.dumps(diag.get("static", {}), indent=2))
    lines.append("```")

    lines.extend(["", "## Layout import check", ""])
    lines.append("```json")
    layout_small = dict(diag.get("layout_import", {}))
    if "ids" in layout_small and isinstance(layout_small["ids"], list):
        layout_small["ids"] = layout_small["ids"][:120]
    lines.append(json.dumps(layout_small, indent=2))
    lines.append("```")

    lines.extend(["", "## Capital method check", ""])
    lines.append("```json")
    lines.append(json.dumps(diag.get("capital_methods", {}), indent=2))
    lines.append("```")

    lines.extend(["", "## App runtime callback-map check", ""])
    runtime_small = dict(diag.get("app_runtime", {}))
    if "app_layout_ids" in runtime_small and isinstance(runtime_small["app_layout_ids"], list):
        runtime_small["app_layout_ids"] = runtime_small["app_layout_ids"][:160]
    lines.append("```json")
    lines.append(json.dumps(runtime_small, indent=2))
    lines.append("```")

    lines.extend(
        [
            "",
            "## What to paste back",
            "",
            "Paste the terminal output and, if needed, these fields from the markdown report:",
            "",
            "- `capital_callback_keys`",
            "- `capital_callback_inputs`",
            "- `app_layout_missing_ids`",
            "- `import_error`",
            "- `recommendations`",
            "",
        ]
    )

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose AI Auto Lab capital summary callback wiring.")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--print-json", action="store_true")
    args = parser.parse_args()

    repo_root = find_repo_root(args.repo_root or Path.cwd())
    live_root = repo_root / "Live"

    diag: dict[str, Any] = {
        "schema_version": "diagnose_auto_lab_capital_callback_v22_2_3",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(repo_root),
        "static": static_checks(repo_root),
        "layout_import": import_auto_lab_layout(repo_root),
        "capital_methods": import_capital_methods(repo_root),
        "app_runtime": import_app_and_check_callback_map(repo_root),
    }
    diag["recommendations"] = make_recommendations(diag)

    out_dir = live_root / "data" / "diagnostics"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "diagnose_auto_lab_capital_callback_v22_2_3.json"
    md_path = out_dir / "diagnose_auto_lab_capital_callback_v22_2_3.md"
    json_path.write_text(json.dumps(diag, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(diag), encoding="utf-8")

    docs_dir = repo_root / "docs" / "patches"
    docs_dir.mkdir(parents=True, exist_ok=True)
    changelog_path = docs_dir / "diagnose_auto_lab_capital_callback_v22_2_3.md"
    changelog_path.write_text(CHANGELOG.strip() + "\n", encoding="utf-8")

    print("v22.2.3 Auto Lab capital callback diagnostic complete.")
    print(f"- repo_root: {repo_root}")
    print(f"- json_report: {json_path}")
    print(f"- markdown_report: {md_path}")
    print(f"- changelog: {changelog_path}")
    print()
    print("Key checks:")
    print(f"- layout_import_ok: {diag['layout_import'].get('ok')}")
    print(f"- layout_missing_ids: {diag['layout_import'].get('missing_ids')}")
    print(f"- capital_methods_ok: {diag['capital_methods'].get('ok')}")
    print(f"- capital_markdown_dynamic: {diag['capital_methods'].get('dynamic_markdown_contains_sample_values')}")
    print(f"- app_import_ok: {diag['app_runtime'].get('ok')}")
    print(f"- app_import_error: {diag['app_runtime'].get('import_error')}")
    print(f"- app_object_found: {diag['app_runtime'].get('app_object_found')}")
    print(f"- callback_count: {diag['app_runtime'].get('callback_count')}")
    print(f"- capital_callback_keys: {diag['app_runtime'].get('capital_callback_keys')}")
    print(f"- capital_callback_inputs: {diag['app_runtime'].get('capital_callback_inputs')}")
    print(f"- capital_callback_states: {diag['app_runtime'].get('capital_callback_states')}")
    print(f"- app_layout_missing_ids: {diag['app_runtime'].get('app_layout_missing_ids')}")
    print()
    print("Recommendations:")
    for rec in diag["recommendations"]:
        print(f"- {rec}")

    if args.print_json:
        print(json.dumps(diag, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
