from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from services.ai.auto_lab_orchestrator.models import local_now_iso, local_run_timestamp, utc_now_iso


def _safe_name(value: str) -> str:
    out = []
    for ch in value:
        if ch.isalnum() or ch in {"_", "-"}:
            out.append(ch)
        else:
            out.append("_")
    return "".join(out).strip("_")[:80] or "symbol_discovery"


def render_symbol_discovery_markdown(packet: dict[str, Any]) -> str:
    symbols = packet.get("suggested_symbols", [])
    rows = packet.get("ranked_candidates", [])

    lines = [
        "# AI Symbol Discovery Report",
        "",
        "**Research/simulation only. This suggests symbols to test; it is not a trade recommendation.**",
        "",
        f"- Generated at: `{packet.get('generated_at', '')}`",
        f"- Seed symbols: `{', '.join(packet.get('seed_symbols', [])) or 'none'}`",
        f"- Theme/focus: `{packet.get('theme', '') or 'none'}`",
        f"- Theme hits: `{', '.join(packet.get('theme_hits', [])) or 'none'}`",
        f"- Suggested universe: `{', '.join(symbols)}`",
        "",
        "## Ranked suggestions",
        "",
        "| Rank | Symbol | Score | Source | Reason | Tags |",
        "|---:|---|---:|---|---|---|",
    ]

    for idx, row in enumerate(rows, start=1):
        lines.append(
            f"| {idx} | `{row.get('symbol')}` | {float(row.get('score', 0.0)):.2f} | "
            f"{row.get('source', '')} | {row.get('reason', '')} | {', '.join(row.get('tags', []))} |"
        )

    lines.extend(
        [
            "",
            "## How Auto Lab should use this",
            "",
            "1. Review the suggested universe.",
            "2. Edit/remove any symbols you do not want.",
            "3. Run Universe Auto Lab.",
            "4. Run Walk-Forward Validation before trusting any result.",
            "",
            "The discovery engine expands research ideas; it does not override validation.",
        ]
    )

    return "\n".join(lines) + "\n"


def write_symbol_discovery_reports(live_root: Path, packet: dict[str, Any]) -> dict[str, str]:
    base = live_root / "data" / "auto_lab_symbol_discovery"
    base.mkdir(parents=True, exist_ok=True)

    first = packet.get("suggested_symbols", ["symbols"])[0] if packet.get("suggested_symbols") else "symbols"
    run_id = f"{local_run_timestamp()}_symbol_discovery_{_safe_name(str(first))}"
    run_dir = base / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    json_path = run_dir / "suggested_universe.json"
    report_path = run_dir / "symbol_discovery_report.md"
    manifest_path = run_dir / "00_ui_run_manifest.json"

    report_md = render_symbol_discovery_markdown(packet)

    json_path.write_text(json.dumps(packet, indent=2), encoding="utf-8")
    report_path.write_text(report_md, encoding="utf-8")

    manifest = {
        "schema_version": "auto_lab_symbol_discovery_manifest_v22_3",
        "generated_at": local_now_iso(),
        "generated_at_utc": utc_now_iso(),
        "run_id": run_id,
        "run_dir": str(run_dir),
        "suggested_symbols": packet.get("suggested_symbols", []),
        "report_path": str(report_path),
        "json_path": str(json_path),
        "human_note": "Markdown is for humans. JSON is for the app/UI.",
        "safety_note": packet.get("safety_note", ""),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return {
        "run_dir": str(run_dir),
        "report_path": str(report_path),
        "json_path": str(json_path),
        "manifest_path": str(manifest_path),
        "report_md": report_md,
    }
