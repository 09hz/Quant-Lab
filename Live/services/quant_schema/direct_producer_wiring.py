from __future__ import annotations

import importlib
import sys
from typing import Any

from services.quant_schema.producer_runtime import wire_namespace, direct_wiring_enabled


KNOWN_PRODUCER_MODULES = [
    "core.BackTestEngine",
    "core.StrategyEngine",
    "services.ai.auto_lab_orchestrator.auto_lab_main_callbacks",
    "services.ai.auto_lab_orchestrator.universe_runner",
    "services.ai.auto_lab_orchestrator.walk_forward",
    "services.ai.auto_lab_orchestrator.market_memory_packet_loader",
    "services.ai.market_memory.research_packet",
    "services.ai.market_memory.build_research_packet",
    "services.ai.market_memory.reports",
]


TARGET_PREFIXES = (
    "core.BackTestEngine",
    "core.StrategyEngine",
    "services.ai.auto_lab_orchestrator",
    "services.ai.research_autolab",
    "services.ai.market_memory",
)


INSTALLED = False


def _try_import(name: str):
    try:
        return importlib.import_module(name)
    except Exception:
        return None


def install_direct_producer_wiring() -> dict[str, Any]:
    global INSTALLED

    if INSTALLED:
        return {"status": "already_installed", "wrapped": 0}
    if not direct_wiring_enabled():
        return {"status": "disabled", "wrapped": 0}

    for module_name in KNOWN_PRODUCER_MODULES:
        _try_import(module_name)

    total = 0
    modules: dict[str, int] = {}

    for module_name, module in list(sys.modules.items()):
        if not module_name.startswith(TARGET_PREFIXES):
            continue
        namespace = getattr(module, "__dict__", None)
        if not isinstance(namespace, dict):
            continue
        result = wire_namespace(module_name, namespace)
        count = int(result.get("wrapped") or 0)
        if count:
            modules[module_name] = count
            total += count

    INSTALLED = True
    if total:
        print(f"[v24.6 direct producer wiring] installed: {modules}")

    return {"status": "installed", "wrapped": total, "modules": modules}
