from __future__ import annotations

from pathlib import Path
import sys


class AutoLabSafetyError(RuntimeError):
    pass


FORBIDDEN_RUNTIME_MODULE_FRAGMENTS = (
    "alpaca",
    "ib_insync",
    "interactivebrokers",
    "robinhood",
    "tdameritrade",
    "schwab",
)


def assert_simulation_only(simulation_only: bool = True) -> None:
    if not simulation_only:
        raise AutoLabSafetyError("Auto Lab orchestrator is simulation/research only.")


def assert_no_live_broker_modules_loaded() -> None:
    loaded = sorted(sys.modules)
    matches = [
        name for name in loaded
        if any(fragment in name.lower() for fragment in FORBIDDEN_RUNTIME_MODULE_FRAGMENTS)
    ]
    if matches:
        raise AutoLabSafetyError(
            "Potential broker/live-order modules are loaded; Auto Lab refuses to run: "
            + ", ".join(matches[:20])
        )


def assert_safe_output_path(path: Path, live_root: Path) -> None:
    path = path.resolve()
    live_root = live_root.resolve()
    allowed_roots = [
        live_root / "data" / "auto_lab_runs",
        live_root / "data" / "autolab_payload",
    ]
    if not any(str(path).lower().startswith(str(root.resolve()).lower()) for root in allowed_roots):
        raise AutoLabSafetyError(
            f"Unsafe Auto Lab output path: {path}. "
            "Allowed roots are Live/data/auto_lab_runs and Live/data/autolab_payload."
        )


def safety_banner() -> str:
    return (
        "AI Auto Lab is research/simulation-only. "
        "It does not place orders, connect to brokers, or provide personalized financial advice."
    )
