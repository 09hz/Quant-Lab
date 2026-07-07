from __future__ import annotations

from pathlib import Path
import ast
import inspect
import re
import sys


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _collect_ids(component):
    found = set()
    stack = [component]
    while stack:
        item = stack.pop()
        if item is None:
            continue
        if isinstance(item, (list, tuple)):
            stack.extend(item)
            continue
        item_id = getattr(item, "id", None)
        if item_id:
            found.add(str(item_id))
        children = getattr(item, "children", None)
        if isinstance(children, (list, tuple)):
            stack.extend(children)
        elif children is not None:
            stack.append(children)
    return found


def _can_call_without_required_args(fn) -> bool:
    try:
        sig = inspect.signature(fn)
    except Exception:
        return False
    for param in sig.parameters.values():
        if (
            param.default is inspect._empty
            and param.kind in {param.POSITIONAL_ONLY, param.POSITIONAL_OR_KEYWORD, param.KEYWORD_ONLY}
        ):
            return False
    return True


def main() -> int:
    repo_root = _repo_root()
    live_root = repo_root / "Live"
    ui_dir = live_root / "ui"
    orch_dir = live_root / "services" / "ai" / "auto_lab_orchestrator"

    required = [
        ui_dir / "auto_lab_memory_packet_ui.py",
        ui_dir / "auto_lab_ui.py",
        orch_dir / "market_memory_packet_loader.py",
        orch_dir / "market_memory_packet_callbacks.py",
        orch_dir / "auto_lab_main_callbacks.py",
    ]
    for path in required:
        if not path.exists():
            print(f"Missing required file: {path}")
            return 2
        ast.parse(path.read_text(encoding="utf-8", errors="replace"))

    if str(live_root) not in sys.path:
        sys.path.insert(0, str(live_root))

    from ui.auto_lab_memory_packet_ui import build_market_memory_packet_panel
    from services.ai.auto_lab_orchestrator.market_memory_packet_loader import (
        format_packet_preview,
        load_or_build_market_memory_packet,
        packet_symbols_csv,
    )
    import ui.auto_lab_ui as auto_lab_ui

    panel_ids = _collect_ids(build_market_memory_packet_panel())
    required_ids = {
        "main-autolab-memory-packet-panel",
        "main-autolab-memory-load-btn",
        "main-autolab-memory-apply-symbols-btn",
        "main-autolab-memory-packet-preview",
    }
    missing = required_ids.difference(panel_ids)
    if missing:
        print(f"Standalone panel missing IDs: {sorted(missing)}")
        return 3

    discovered_ids = set()
    for name, obj in vars(auto_lab_ui).items():
        if str(name).startswith("_"):
            continue
        if hasattr(obj, "children") or hasattr(obj, "to_plotly_json"):
            discovered_ids.update(_collect_ids(obj))
        if callable(obj) and _can_call_without_required_args(obj):
            lowered = str(name).lower()
            if any(token in lowered for token in ["layout", "tab", "page", "ui", "auto_lab", "autolab"]):
                try:
                    discovered_ids.update(_collect_ids(obj()))
                except Exception:
                    pass

    if "main-autolab-memory-packet-panel" not in discovered_ids:
        print("Market Memory panel not detected in callable/module-level Auto Lab layout objects.")
        print(f"Detected IDs sample: {sorted(discovered_ids)[:120]}")
        return 4

    callbacks_text = (orch_dir / "auto_lab_main_callbacks.py").read_text(encoding="utf-8", errors="replace")
    symbol_id_match = re.search(r'_V23_2_2_MEMORY_SYMBOL_INPUT_ID\s*=\s*["\']([^"\']+)["\']', callbacks_text)
    if not symbol_id_match:
        print("Could not find v23.2.2 callback symbol input ID marker.")
        return 5

    packet_result = load_or_build_market_memory_packet(
        live_root=live_root,
        theme="AI infrastructure semiconductors",
        max_symbols=12,
        rebuild=True,
    )
    packet = packet_result.get("packet") or {}
    symbols = packet_symbols_csv(packet)
    preview = format_packet_preview(packet_result)

    if not symbols:
        print("Market Memory packet has no symbols.")
        return 6
    if "Loaded Market Memory Research Packet" not in preview:
        print("Preview markdown missing expected heading.")
        return 7

    forbidden = {"AI", "RSI", "BUY", "PASS", "ENV", "WARN", "SEND", "LIVE"}
    bad = forbidden.intersection({item.strip().upper() for item in symbols.split(",") if item.strip()})
    if bad:
        print(f"Packet contains noisy symbols: {bad}")
        return 8

    print("v23.2.2 Complete Market Memory Panel Repair self-test: PASS")
    print(f"detected_symbol_input_id: {symbol_id_match.group(1)}")
    print(f"packet_quality_score: {packet.get('packet_quality_score')}")
    print(f"packet_warning_flags: {packet.get('warning_flags')}")
    print(f"suggested_symbols: {symbols}")
    print(f"packet_json_path: {packet_result.get('json_path')}")
    print("Research/simulation only. No broker calls or trade execution were made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
