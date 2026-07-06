#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CHANGELOG = """# diagnose_auto_lab_ui_overlap_v22_1

Read-only diagnostic for integrating the new AI Auto Lab tab into the main Dash app.

It inspects:
- Live/app.py
- Live/callbacks.py
- Live/ui/
- Live/assets/
- old Research Auto Lab files
- new Auto Lab orchestrator/UI files
- tab labels/values
- callback IDs
- imports
- CSS overlap

It writes:
- Live/data/diagnostics/diagnose_auto_lab_ui_overlap_v22_1.json
- Live/data/diagnostics/diagnose_auto_lab_ui_overlap_v22_1.md
- docs/patches/diagnose_auto_lab_ui_overlap_v22_1.md

Safety:
- Read-only for app code.
- No backups.
- No broker calls.
- No live orders.
"""


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


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


def file_info(path: Path, root: Path) -> dict[str, Any]:
    return {
        "path": rel(path, root),
        "exists": path.exists(),
        "is_dir": path.is_dir(),
        "size": path.stat().st_size if path.exists() and path.is_file() else None,
    }


def discover_python_files(base: Path) -> list[Path]:
    if not base.exists():
        return []
    return sorted(p for p in base.rglob("*.py") if p.is_file())


def discover_assets(base: Path) -> list[Path]:
    if not base.exists():
        return []
    return sorted(p for p in base.rglob("*") if p.is_file())


def line_matches(path: Path, patterns: list[str], root: Path, limit: int = 200) -> list[dict[str, Any]]:
    text = read_text(path)
    if not text:
        return []
    compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
    out = []
    for i, line in enumerate(text.splitlines(), start=1):
        if any(p.search(line) for p in compiled):
            out.append({"file": rel(path, root), "line": i, "text": line.strip()[:1000]})
            if len(out) >= limit:
                break
    return out


def extract_dash_ids(text: str) -> list[str]:
    ids = set()
    for m in re.finditer(r"\bid\s*=\s*['\"]([^'\"]+)['\"]", text):
        ids.add(m.group(1))
    for m in re.finditer(r"\b(?:Output|Input|State)\s*\(\s*['\"]([^'\"]+)['\"]", text):
        ids.add(m.group(1))
    for m in re.finditer(r"\bid\s*=\s*\{([^}]+)\}", text, flags=re.DOTALL):
        ids.add("DICT_ID:" + re.sub(r"\s+", " ", m.group(1)).strip()[:120])
    return sorted(ids)


def classify_ids(ids: list[str]) -> dict[str, list[str]]:
    groups = {"auto_lab_related": [], "research_related": [], "tab_related": [], "other": []}
    for item in ids:
        low = item.lower()
        if "auto" in low and "lab" in low:
            groups["auto_lab_related"].append(item)
        elif "research" in low or "news" in low or "brief" in low:
            groups["research_related"].append(item)
        elif "tab" in low or "tabs" in low:
            groups["tab_related"].append(item)
        else:
            groups["other"].append(item)
    return groups


def extract_tabs_from_text(text: str, path: Path, root: Path) -> list[dict[str, Any]]:
    out = []
    for m in re.finditer(r"(?:dcc|dbc)\.Tab\s*\((?P<body>.*?)\)", text, flags=re.DOTALL):
        body = m.group("body")
        label = re.search(r"\blabel\s*=\s*['\"]([^'\"]+)['\"]", body)
        value = re.search(r"\bvalue\s*=\s*['\"]([^'\"]+)['\"]", body)
        ident = re.search(r"\bid\s*=\s*['\"]([^'\"]+)['\"]", body)
        if label or value or ident:
            out.append({
                "file": rel(path, root),
                "line": text[:m.start()].count("\n") + 1,
                "label": label.group(1) if label else "",
                "value": value.group(1) if value else "",
                "id": ident.group(1) if ident else "",
                "raw": re.sub(r"\s+", " ", body).strip()[:500],
            })
    for m in re.finditer(r"['\"]tab-[^'\"]+['\"]|['\"][^'\"]*auto[^'\"]*lab[^'\"]*['\"]|['\"][^'\"]*research[^'\"]*['\"]", text, flags=re.IGNORECASE):
        out.append({"file": rel(path, root), "line": text[:m.start()].count("\n") + 1, "literal": m.group(0)})
    return out


def extract_callbacks(text: str, path: Path, root: Path) -> list[dict[str, Any]]:
    lines = text.splitlines()
    out = []
    for i, line in enumerate(lines, start=1):
        if "@app.callback" in line or "@callback" in line:
            block = [line]
            for j in range(i + 1, min(len(lines), i + 18) + 1):
                block.append(lines[j - 1])
                if lines[j - 1].lstrip().startswith("def "):
                    break
            block_text = "\n".join(block)
            if any(token in block_text.lower() for token in ["auto", "research", "tab", "news", "brief"]):
                out.append({"file": rel(path, root), "line": i, "block": block_text[:3000]})
    return out


def ast_imports(path: Path, root: Path) -> list[dict[str, Any]]:
    text = read_text(path)
    if not text:
        return []
    try:
        tree = ast.parse(text)
    except Exception as exc:
        return [{"file": rel(path, root), "parse_error": str(exc)}]
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                s = alias.name
                if "auto" in s.lower() or "research" in s.lower():
                    out.append({"file": rel(path, root), "line": node.lineno, "import": s})
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = ", ".join(alias.name for alias in node.names)
            s = f"{module} {names}"
            if "auto" in s.lower() or "research" in s.lower():
                out.append({"file": rel(path, root), "line": node.lineno, "from": module, "import": names})
    return out


def build_diagnostic(repo_root: Path) -> dict[str, Any]:
    live_root = repo_root / "Live"
    app_py = live_root / "app.py"
    callbacks_py = live_root / "callbacks.py"
    ui_dir = live_root / "ui"
    assets_dir = live_root / "assets"
    old_ui = ui_dir / "research_autolab_ui.py"
    old_service = live_root / "services" / "ai" / "research_autolab"
    new_pkg = live_root / "services" / "ai" / "auto_lab_orchestrator"

    key_files = [
        app_py,
        callbacks_py,
        old_ui,
        new_pkg / "auto_lab_ui_launcher.py",
        new_pkg / "ui_report_loader.py",
        new_pkg / "universe_runner.py",
        new_pkg / "walk_forward_runner.py",
    ]

    py_files = [app_py, callbacks_py] + discover_python_files(ui_dir) + discover_python_files(live_root / "services" / "ai")
    py_files = sorted(set(p for p in py_files if p.exists()))

    tab_matches, import_matches, callback_matches, mentions = [], [], [], []
    id_groups = {}

    for path in py_files:
        text = read_text(path)
        if not text:
            continue
        tab_matches.extend(extract_tabs_from_text(text, path, repo_root))
        import_matches.extend(ast_imports(path, repo_root))
        callback_matches.extend(extract_callbacks(text, path, repo_root))

        ids = extract_dash_ids(text)
        classified = classify_ids(ids)
        if classified["auto_lab_related"] or classified["research_related"] or classified["tab_related"]:
            id_groups[rel(path, repo_root)] = classified

        mentions.extend(line_matches(path, [r"auto[_-]?lab", r"research[_-]?autolab", r"Research Auto Lab", r"AI Auto Lab", r"dcc\.Tabs", r"dcc\.Tab", r"dbc\.Tab", r"tab"], repo_root, limit=80))

    css_files = [p for p in discover_assets(assets_dir) if p.suffix.lower() in {".css", ".scss"}]
    css_mentions = []
    for css in css_files:
        css_mentions.extend(line_matches(css, [r"auto[_-]?lab", r"research", r"tab", r"newsroom", r"dashboard"], repo_root, limit=50))

    recs = []
    if not app_py.exists():
        recs.append("BLOCKER: Live/app.py not found.")
    if not callbacks_py.exists():
        recs.append("NOTE: Live/callbacks.py not found; callbacks may be registered elsewhere.")
    if old_ui.exists() or old_service.exists():
        recs.append("Do not delete old Research Auto Lab yet. Hide/deprecate first because references may still exist.")
    if not (new_pkg / "universe_runner.py").exists():
        recs.append("BLOCKER: v21.5 universe_runner.py missing.")
    if not (new_pkg / "walk_forward_runner.py").exists():
        recs.append("BLOCKER: v21.6 walk_forward_runner.py missing.")
    if not (new_pkg / "ui_report_loader.py").exists():
        recs.append("BLOCKER: v22.0 ui_report_loader.py missing.")
    if not (assets_dir / "auto_lab.css").exists():
        recs.append("Add dedicated CSS at Live/assets/auto_lab.css.")
    else:
        recs.append("Live/assets/auto_lab.css already exists; patch should update, not duplicate.")
    recs.append("Recommended v22.1 integration: top-level tab labeled 'AI Auto Lab'.")
    recs.append("Recommended old tab handling: hide/deprecate old Research Auto Lab; remove only after new tab is stable.")

    return {
        "schema_version": "diagnose_auto_lab_ui_overlap_v22_1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(repo_root),
        "live_root": str(live_root),
        "key_files": [file_info(p, repo_root) for p in key_files],
        "directories": {
            "ui_dir": file_info(ui_dir, repo_root),
            "assets_dir": file_info(assets_dir, repo_root),
            "old_research_autolab_service": file_info(old_service, repo_root),
            "new_auto_lab_orchestrator": file_info(new_pkg, repo_root),
        },
        "old_research_autolab_files": [file_info(p, repo_root) for p in discover_python_files(old_service)],
        "new_auto_lab_files": [file_info(p, repo_root) for p in discover_python_files(new_pkg)],
        "css_files": [file_info(p, repo_root) for p in css_files],
        "tab_matches": tab_matches[:500],
        "auto_lab_import_matches": import_matches[:500],
        "relevant_callback_matches": callback_matches[:500],
        "dash_id_groups": id_groups,
        "auto_lab_mentions": mentions[:1000],
        "css_mentions": css_mentions[:500],
        "recommendations": recs,
    }


def render_markdown(diag: dict[str, Any]) -> str:
    lines = [
        "# v22.1 Auto Lab UI Overlap Diagnostic",
        "",
        "Read-only diagnostic for integrating the new AI Auto Lab tab into the main Dash app.",
        "",
        f"- generated_at: `{diag.get('generated_at')}`",
        f"- repo_root: `{diag.get('repo_root')}`",
        "",
        "## Recommendations",
        "",
    ]
    lines += [f"- {x}" for x in diag.get("recommendations", [])]

    lines += ["", "## Key files", "", "| Path | Exists | Size |", "|---|---|---:|"]
    for item in diag.get("key_files", []):
        lines.append(f"| {item.get('path')} | {item.get('exists')} | {item.get('size')} |")

    lines += ["", "## Existing tab matches", ""]
    for item in diag.get("tab_matches", [])[:150]:
        lines.append(f"- `{item.get('file')}` line {item.get('line')}: `{item}`")
    if not diag.get("tab_matches"):
        lines.append("No tab matches found by regex. Manual inspection may be needed.")

    lines += ["", "## Auto Lab import matches", ""]
    for item in diag.get("auto_lab_import_matches", [])[:150]:
        lines.append(f"- `{item.get('file')}` line {item.get('line')}: `{item}`")
    if not diag.get("auto_lab_import_matches"):
        lines.append("No auto-lab/research related imports found.")

    lines += ["", "## Relevant callback matches", ""]
    for item in diag.get("relevant_callback_matches", [])[:80]:
        block = str(item.get("block", "")).replace("\n", " / ")
        lines.append(f"- `{item.get('file')}` line {item.get('line')}: `{block[:500]}`")
    if not diag.get("relevant_callback_matches"):
        lines.append("No relevant callbacks found by regex.")

    lines += ["", "## Dash ID groups", ""]
    groups = diag.get("dash_id_groups") or {}
    for file, group in groups.items():
        lines.append(f"### `{file}`")
        for group_name in ["auto_lab_related", "research_related", "tab_related"]:
            values = group.get(group_name) or []
            if values:
                lines.append(f"- {group_name}: `{', '.join(values[:80])}`")
        lines.append("")
    if not groups:
        lines.append("No relevant Dash IDs found.")

    lines += ["", "## CSS files", "", "| Path | Size |", "|---|---:|"]
    for item in diag.get("css_files", []):
        lines.append(f"| {item.get('path')} | {item.get('size')} |")

    lines += ["", "## Old Research Auto Lab files", "", "| Path | Exists | Size |", "|---|---|---:|"]
    for item in diag.get("old_research_autolab_files", []):
        lines.append(f"| {item.get('path')} | {item.get('exists')} | {item.get('size')} |")

    lines += ["", "## New Auto Lab files", "", "| Path | Exists | Size |", "|---|---|---:|"]
    for item in diag.get("new_auto_lab_files", [])[:150]:
        lines.append(f"| {item.get('path')} | {item.get('exists')} | {item.get('size')} |")

    lines += [
        "",
        "## Integration plan",
        "",
        "1. Add `Live/ui/auto_lab_ui.py` for the main-app tab layout.",
        "2. Add `Live/services/ai/auto_lab_orchestrator/auto_lab_main_callbacks.py` for callbacks.",
        "3. Add `Live/assets/auto_lab.css` for dedicated styling.",
        "4. Patch `Live/app.py` at the detected tab container.",
        "5. Hide/deprecate old Research Auto Lab references; do not delete yet.",
        "",
        "## Safety",
        "",
        "Diagnostic only. No broker calls, no order routing, no live trading behavior.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose v22.1 Auto Lab main Dash integration.")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--print-json", action="store_true")
    args = parser.parse_args()

    repo_root = find_repo_root(args.repo_root or Path.cwd())
    live_root = repo_root / "Live"
    diag = build_diagnostic(repo_root)

    out_dir = live_root / "data" / "diagnostics"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "diagnose_auto_lab_ui_overlap_v22_1.json"
    md_path = out_dir / "diagnose_auto_lab_ui_overlap_v22_1.md"
    json_path.write_text(json.dumps(diag, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(diag), encoding="utf-8")

    docs_dir = repo_root / "docs" / "patches"
    docs_dir.mkdir(parents=True, exist_ok=True)
    docs_path = docs_dir / "diagnose_auto_lab_ui_overlap_v22_1.md"
    docs_path.write_text(CHANGELOG.strip() + "\n", encoding="utf-8")

    print("v22.1 Auto Lab UI overlap diagnostic complete.")
    print(f"repo_root: {repo_root}")
    print(f"json_report: {json_path}")
    print(f"markdown_report: {md_path}")
    print(f"diagnostic_changelog: {docs_path}")
    print()
    print("Key recommendations:")
    for item in diag.get("recommendations", []):
        print(f"- {item}")
    print()
    print("Counts:")
    print(f"- tab_matches: {len(diag.get('tab_matches', []))}")
    print(f"- auto_lab_import_matches: {len(diag.get('auto_lab_import_matches', []))}")
    print(f"- relevant_callback_matches: {len(diag.get('relevant_callback_matches', []))}")
    print(f"- css_files: {len(diag.get('css_files', []))}")
    print(f"- old_research_autolab_files: {len(diag.get('old_research_autolab_files', []))}")
    print(f"- new_auto_lab_files: {len(diag.get('new_auto_lab_files', []))}")

    if args.print_json:
        print(json.dumps(diag, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
