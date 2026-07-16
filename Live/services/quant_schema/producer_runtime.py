from __future__ import annotations

import functools
import inspect
import os
from pathlib import Path
import re
from typing import Any


DIRECT_WIRING_MARKER = "_quant_producer_wired_v24_6"


PRODUCER_ACTION_WORDS = {
    "run",
    "execute",
    "build",
    "generate",
    "create",
    "save",
    "export",
    "evaluate",
    "score",
    "rank",
    "select",
    "simulate",
    "process",
    "analyze",
    "analyse",
    "load",
}


CATEGORY_WORDS = {
    "backtest": "backtest",
    "back_test": "backtest",
    "walk_forward": "walk_forward",
    "walk-forward": "walk_forward",
    "walkforward": "walk_forward",
    "universe": "universe",
    "auto_lab": "auto_lab",
    "autolab": "auto_lab",
    "research_autolab": "auto_lab",
    "market_memory": "market_memory",
    "research_packet": "market_memory",
    "memory_report": "market_memory",
    "strategy": "strategy",
    "signal": "strategy",
}


def direct_wiring_enabled() -> bool:
    if os.environ.get("ALGOTRADER_ENABLE_QUANT_WIRING", "1").strip().lower() in {"0", "false", "no", "off"}:
        return False
    return os.environ.get("ALGOTRADER_ENABLE_DIRECT_PRODUCER_WIRING", "1").strip().lower() not in {"0", "false", "no", "off"}


def infer_category(module_name: str, member_name: str | None = None) -> str | None:
    """Infer result category.

    Member/function names get priority over module names. This prevents a
    module such as core.BackTestEngine from forcing every wrapped function to
    be classified as a backtest when the member name is more specific, for
    example run_universe -> universe.
    """
    member_text = (member_name or "").lower()
    module_text = module_name.lower()

    if member_text:
        for needle, category in CATEGORY_WORDS.items():
            if needle in member_text:
                return category

    for needle, category in CATEGORY_WORDS.items():
        if needle in module_text:
            return category

    return None


def _tokenize_name(value: str) -> set[str]:
    return {token for token in re.split(r"[^a-zA-Z0-9]+|_", value.lower()) if token}


def looks_like_producer_name(name: str, category: str | None) -> bool:
    lowered = name.lower()
    if name.startswith("__"):
        return False
    if lowered in {"main", "app", "layout"}:
        return False
    if lowered.startswith("register") and "result" not in lowered and "run" not in lowered:
        return False

    tokens = _tokenize_name(lowered)
    if tokens.intersection(PRODUCER_ACTION_WORDS):
        return True

    if category and any(word in lowered for word in CATEGORY_WORDS):
        return True

    return any(word in lowered for word in ["backtest", "walk_forward", "universe", "autolab", "auto_lab", "packet", "report", "strategy"])


def looks_captureable(result: Any) -> bool:
    if result is None:
        return False
    if isinstance(result, (str, int, float, bool, bytes)):
        return False
    if isinstance(result, (dict, list, tuple)):
        return True
    if hasattr(result, "to_dict") or hasattr(result, "to_json") or hasattr(result, "to_csv"):
        return True
    return False


def capture_producer_result(
    category: str,
    result: Any,
    *,
    context: dict[str, Any],
    repo_root: str | Path | None = None,
    preferred_backend: str | None = None,
) -> None:
    try:
        from services.quant_schema.result_capture import capture_research_result

        capture = capture_research_result(
            category=category,
            payload=result,
            context=context,
            repo_root=repo_root,
            preferred_backend=preferred_backend,
        )
        if getattr(capture, "status", None) not in {"captured"}:
            print(f"[v24.6 direct producer wiring] capture status={getattr(capture, 'status', None)} error={getattr(capture, 'error', None)}")
    except Exception as exc:
        print(f"[v24.6 direct producer wiring] capture skipped: {type(exc).__name__}: {exc}")


def _function_belongs_to_module(fn: Any, module_name: str) -> bool:
    fn_module = getattr(fn, "__module__", None)
    if fn_module is None:
        return True
    return fn_module == module_name or fn_module.endswith("." + module_name.split(".")[-1])


def _wrap_function(
    fn: Any,
    *,
    module_name: str,
    member_name: str,
    category: str,
    repo_root: str | Path | None = None,
    preferred_backend: str | None = None,
):
    if getattr(fn, DIRECT_WIRING_MARKER, False) or getattr(fn, "_quant_wired_v24_5", False):
        return fn, False

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any):
        result = fn(*args, **kwargs)
        if looks_captureable(result):
            context = {
                "module": module_name,
                "method": member_name,
                "category": category,
                "runtime_hook": "v24.6_direct_producer",
            }
            capture_producer_result(
                category,
                result,
                context=context,
                repo_root=repo_root,
                preferred_backend=preferred_backend,
            )
        return result

    setattr(wrapper, DIRECT_WIRING_MARKER, True)
    setattr(wrapper, "_quant_wired_v24_5", True)
    return wrapper, True


def _wrap_module_function(
    namespace: dict[str, Any],
    name: str,
    category: str,
    module_name: str,
    repo_root: str | Path | None,
    preferred_backend: str | None,
) -> bool:
    fn = namespace.get(name)
    if not inspect.isfunction(fn):
        return False
    if not _function_belongs_to_module(fn, module_name):
        return False
    wrapped, changed = _wrap_function(
        fn,
        module_name=module_name,
        member_name=name,
        category=category,
        repo_root=repo_root,
        preferred_backend=preferred_backend,
    )
    if changed:
        namespace[name] = wrapped
    return changed


def _wrap_class_method(
    cls: type,
    method_name: str,
    category: str,
    module_name: str,
    repo_root: str | Path | None,
    preferred_backend: str | None,
) -> bool:
    try:
        raw = inspect.getattr_static(cls, method_name)
    except Exception:
        return False

    descriptor_type = None
    fn = raw
    if isinstance(raw, staticmethod):
        descriptor_type = staticmethod
        fn = raw.__func__
    elif isinstance(raw, classmethod):
        descriptor_type = classmethod
        fn = raw.__func__

    if not callable(fn):
        return False
    if inspect.isfunction(fn) and not _function_belongs_to_module(fn, module_name):
        return False

    wrapped, changed = _wrap_function(
        fn,
        module_name=f"{module_name}.{cls.__name__}",
        member_name=method_name,
        category=category,
        repo_root=repo_root,
        preferred_backend=preferred_backend,
    )
    if not changed:
        return False

    try:
        if descriptor_type is staticmethod:
            setattr(cls, method_name, staticmethod(wrapped))
        elif descriptor_type is classmethod:
            setattr(cls, method_name, classmethod(wrapped))
        else:
            setattr(cls, method_name, wrapped)
        return True
    except Exception:
        return False


def wire_namespace(
    module_name: str,
    namespace: dict[str, Any],
    *,
    repo_root: str | Path | None = None,
    preferred_backend: str | None = None,
) -> dict[str, Any]:
    if not direct_wiring_enabled():
        return {"status": "disabled", "wrapped": 0, "module": module_name}

    wrapped = 0
    wrapped_members: list[str] = []

    for name, value in list(namespace.items()):
        category = infer_category(module_name, name)
        if not category:
            continue
        if not looks_like_producer_name(name, category):
            continue

        if inspect.isfunction(value):
            if _wrap_module_function(namespace, name, category, module_name, repo_root, preferred_backend):
                wrapped += 1
                wrapped_members.append(name)
        elif inspect.isclass(value):
            for method_name, _method_value in list(vars(value).items()):
                method_category = infer_category(f"{module_name}.{value.__name__}", method_name) or category
                if method_category and looks_like_producer_name(method_name, method_category):
                    if _wrap_class_method(value, method_name, method_category, module_name, repo_root, preferred_backend):
                        wrapped += 1
                        wrapped_members.append(f"{value.__name__}.{method_name}")

    return {
        "status": "wired",
        "module": module_name,
        "wrapped": wrapped,
        "members": wrapped_members[:50],
    }


def wire_current_module(
    module_name: str,
    namespace: dict[str, Any],
    *,
    repo_root: str | Path | None = None,
    preferred_backend: str | None = None,
) -> dict[str, Any]:
    try:
        return wire_namespace(module_name, namespace, repo_root=repo_root, preferred_backend=preferred_backend)
    except Exception as exc:
        print(f"[v24.6 direct producer wiring] disabled for {module_name}: {type(exc).__name__}: {exc}")
        return {"status": "error", "module": module_name, "wrapped": 0, "error": f"{type(exc).__name__}: {exc}"}
