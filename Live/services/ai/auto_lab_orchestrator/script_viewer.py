from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MAX_MD_CHARS = 65000


def _read_text(path: Path, max_chars: int = MAX_MD_CHARS) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"Could not read `{path}`: {exc}"
    if len(text) > max_chars:
        return text[:max_chars] + "\n\n...[truncated for UI]..."
    return text


def _latest_dir(base: Path) -> Path | None:
    if not base.exists():
        return None
    candidates = [
        path
        for path in base.iterdir()
        if path.is_dir() and not path.name.startswith("_")
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _find_first(run_dir: Path | None, names: list[str]) -> Path | None:
    if not run_dir or not run_dir.exists():
        return None

    for name in names:
        direct = run_dir / name
        if direct.exists():
            return direct

    for name in names:
        matches = sorted(run_dir.rglob(name))
        if matches:
            return matches[0]

    return None


def latest_universe_dir(live_root: Path) -> Path | None:
    return _latest_dir(live_root / "data" / "auto_lab_universe_runs")


def latest_walk_forward_dir(live_root: Path) -> Path | None:
    return _latest_dir(live_root / "data" / "auto_lab_walk_forward_runs")


def build_script_packet(live_root: Path) -> dict[str, Any]:
    universe_dir = latest_universe_dir(live_root)
    walk_dir = latest_walk_forward_dir(live_root)

    universe_file = _find_first(
        universe_dir,
        [
            "top_universe_strategy_algorithm.md",
            "top_strategy_algorithm.md",
            "strategy_build_trace.md",
            "mutation_report.md",
            "universe_report.md",
            "report.md",
        ],
    )
    walk_file = _find_first(
        walk_dir,
        [
            "top_walk_forward_strategy_algorithm.md",
            "top_strategy_algorithm.md",
            "strategy_build_trace.md",
            "overfit_warning_report.md",
            "walk_forward_universe_report.md",
            "report.md",
        ],
    )

    universe_md = (
        _read_text(universe_file)
        if universe_file
        else "No universe strategy algorithm/script report found yet."
    )
    walk_md = (
        _read_text(walk_file)
        if walk_file
        else "No walk-forward strategy algorithm/script report found yet."
    )

    paths = {
        "latest_universe_dir": str(universe_dir) if universe_dir else "",
        "latest_walk_forward_dir": str(walk_dir) if walk_dir else "",
        "universe_script_report": str(universe_file) if universe_file else "",
        "walk_forward_script_report": str(walk_file) if walk_file else "",
    }

    return {
        "universe_md": universe_md,
        "walk_forward_md": walk_md,
        "paths": paths,
    }


def summarize_script_paths(paths: dict[str, Any]) -> str:
    if not paths:
        return "No script paths available."
    lines = []
    for key, value in paths.items():
        lines.append(f"{key}: {value}")
    return "\n".join(lines)


def _friendly_label(run_type: str, context: dict[str, Any]) -> str:
    generated = datetime.now().strftime("%Y-%m-%d_%H%M")
    if run_type == "walk_forward":
        train = f"{context.get('train_start', '')}_to_{context.get('train_end', '')}"
        test = f"{context.get('test_start', '')}_to_{context.get('test_end', '')}"
        return f"{generated}_walk_forward_train_{train}_test_{test}"
    start = context.get("universe_start", "")
    end = context.get("universe_end", "")
    return f"{generated}_universe_{start}_to_{end}"


def write_latest_manifest(
    live_root: Path,
    run_type: str,
    context: dict[str, Any],
    capital: dict[str, Any],
    command: list[str] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, str]:
    """Write human-friendly index files into the latest run directory.

    This does not rename backend output folders yet; it adds a readable index and manifest.
    """
    run_dir = latest_walk_forward_dir(live_root) if run_type == "walk_forward" else latest_universe_dir(live_root)
    if not run_dir:
        return {}

    packet = build_script_packet(live_root)
    manifest = {
        "schema_version": "auto_lab_ui_manifest_v22_2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_type": run_type,
        "friendly_label": _friendly_label(run_type, context),
        "run_dir": str(run_dir),
        "context": context,
        "capital_assumptions": capital,
        "command": command or [],
        "warnings": warnings or [],
        "script_paths": packet.get("paths", {}),
        "human_note": "Markdown files are for humans. JSON files are for the app/UI.",
    }

    manifest_path = run_dir / "00_ui_run_manifest.json"
    index_path = run_dir / "00_human_report_index.md"

    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    index_lines = [
        "# Auto Lab Human Report Index",
        "",
        f"- Friendly label: `{manifest['friendly_label']}`",
        f"- Run type: `{run_type}`",
        f"- Run folder: `{run_dir}`",
        "",
        "## Capital assumptions",
        "",
        f"- Starting cash: `{capital.get('initial_cash')}`",
        f"- Target cash: `{capital.get('target_cash')}`",
        f"- Target return pct: `{capital.get('target_return_pct')}`",
        f"- Cash exposure pct: `{capital.get('cash_exposure_pct')}`",
        f"- Sizing mode: `{capital.get('sizing_mode')}`",
        "",
        "## Important human-readable files",
        "",
    ]

    for key, value in packet.get("paths", {}).items():
        if value:
            index_lines.append(f"- {key}: `{value}`")

    if warnings:
        index_lines.extend(["", "## Notes", ""])
        for item in warnings:
            index_lines.append(f"- {item}")

    index_lines.extend(
        [
            "",
            "## JSON files",
            "",
            "JSON files are kept because the app uses them for tables, charts, run comparison, clickable details, and later Market Memory links.",
        ]
    )

    index_path.write_text("\n".join(index_lines) + "\n", encoding="utf-8")

    return {
        "manifest_path": str(manifest_path),
        "index_path": str(index_path),
        "run_dir": str(run_dir),
    }
