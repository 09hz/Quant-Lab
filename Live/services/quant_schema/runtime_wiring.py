from __future__ import annotations

import functools
import importlib
import inspect
import os
from typing import Any

from services.quant_schema.result_capture import (
    capture_backtest_result,
    capture_auto_lab_result,
    capture_walk_forward_result,
    capture_universe_result,
    capture_strategy_result,
)


INSTALLED = False


TARGET_MODULES = [
    "core.BackTestEngine",
    "core.StrategyEngine",
    "services.ai.auto_lab_orchestrator.auto_lab_main_callbacks",
    "services.ai.auto_lab_orchestrator.universe_runner",
    "services.ai.auto_lab_orchestrator.walk_forward",
    "services.ai.research_autolab",
]


def _enabled() -> bool:
    """Return True only when broad v24.5 runtime hooks are explicitly enabled.

    These broad hooks can wrap too many functions during Dash startup. Direct
    producer wiring remains available through v24.6, but broad startup wrapping
    is now opt-in to prevent recursive capture and slow app loading.
    """
    if os.environ.get("ALGOTRADER_ENABLE_QUANT_WIRING", "1").strip().lower() in {"0", "false", "no", "off"}:
        return False
    return os.environ.get("ALGOTRADER_ENABLE_BROAD_RUNTIME_HOOKS", "0").strip().lower() in {"1", "true", "yes", "on"}

def _category_for_name(module_name: str, attr_name: str) -> str | None:
    text = f"{module_name}.{attr_name}".lower()
    if "backtest" in text or "back_test" in text:
        return "backtest"
    if "walk_forward" in text or "walk-forward" in text:
        return "walk_forward"
    if "universe" in text:
        return "universe"
    if "auto_lab" in text or "autolab" in text:
        return "auto_lab"
    if "strategy" in text:
        return "strategy"
    return None


def _capture(category: str, result: Any, context: dict[str, Any]) -> None:
    try:
        if category == "backtest":
            capture_backtest_result(result, context=context)
        elif category == "walk_forward":
            capture_walk_forward_result(result, context=context)
        elif category == "universe":
            capture_universe_result(result, context=context)
        elif category == "auto_lab":
            capture_auto_lab_result(result, context=context)
        elif category == "strategy":
            capture_strategy_result(result, context=context)
    except Exception as exc:
        print(f"[v24.5 quant wiring] capture skipped: {type(exc).__name__}: {exc}")


def _looks_captureable(result: Any) -> bool:
    if result is None:
        return False
    if isinstance(result, (dict, list, tuple)):
        return True
    if hasattr(result, "to_dict") or hasattr(result, "to_json"):
        return True
    return False


def _wrap_callable(obj: Any, attr_name: str, module_name: str, category: str) -> bool:
    original = getattr(obj, attr_name, None)
    if original is None or getattr(original, "_quant_wired_v24_5", False) or getattr(original, "_quant_producer_wired_v24_6", False):
        return False
    if not callable(original):
        return False

    @functools.wraps(original)
    def wrapper(*args: Any, **kwargs: Any):
        result = original(*args, **kwargs)
        if _looks_captureable(result):
            context = {
                "module": module_name,
                "method": attr_name,
                "category": category,
                "runtime_hook": "v24.5",
            }
            _capture(category, result, context)
        return result

    wrapper._quant_wired_v24_5 = True  # type: ignore[attr-defined]
    try:
        setattr(obj, attr_name, wrapper)
        return True
    except Exception:
        return False


def _wire_module(module_name: str) -> int:
    try:
        module = importlib.import_module(module_name)
    except Exception:
        return 0

    wrapped = 0

    # Wrap module-level functions with recognizable names.
    for attr_name, value in list(vars(module).items()):
        category = _category_for_name(module_name, attr_name)
        if category and inspect.isfunction(value):
            if _wrap_callable(module, attr_name, module_name, category):
                wrapped += 1

    # Wrap class methods with recognizable names.
    for class_name, cls in list(vars(module).items()):
        if not inspect.isclass(cls):
            continue
        for method_name, value in list(vars(cls).items()):
            category = _category_for_name(f"{module_name}.{class_name}", method_name)
            if category and callable(value) and not method_name.startswith("__"):
                if _wrap_callable(cls, method_name, f"{module_name}.{class_name}", category):
                    wrapped += 1

    return wrapped


def install_quant_output_hooks() -> dict[str, Any]:
    global INSTALLED
    if INSTALLED:
        return {"status": "already_installed", "wrapped": 0}
    if not _enabled():
        return {"status": "disabled_by_env", "wrapped": 0}

    total = 0
    modules: dict[str, int] = {}
    for module_name in TARGET_MODULES:
        count = _wire_module(module_name)
        if count:
            modules[module_name] = count
            total += count

    INSTALLED = True
    if total:
        print(f"[v24.5 quant wiring] installed output hooks: {modules}")
    return {"status": "installed", "wrapped": total, "modules": modules}
