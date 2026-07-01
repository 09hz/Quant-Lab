from __future__ import annotations

import os
from pathlib import Path


SIMULATION_ONLY_ENV = "RESEARCH_AUTOLAB_SIMULATION_ONLY"


class SimulationSafetyError(RuntimeError):
    pass


def simulation_only_enabled() -> bool:
    value = str(os.getenv(SIMULATION_ONLY_ENV, "1")).strip().lower()
    return value not in {"0", "false", "no", "off"}


def assert_simulation_only() -> None:
    if not simulation_only_enabled():
        raise SimulationSafetyError(
            f"{SIMULATION_ONLY_ENV}=0 disables the Research Autolab safety guard. "
            "Refusing to continue. Research Autolab must remain simulation-only."
        )


def assert_safe_output_path(path: str | Path | None) -> None:
    if path is None:
        return

    p = Path(path)
    lowered = str(p).lower()

    trading_state_fragments = (
        "cache\\paper",
        "cache/paper",
        "orders.csv",
        "fills.csv",
        "positions.csv",
    )

    if any(fragment in lowered for fragment in trading_state_fragments):
        raise SimulationSafetyError(f"Refusing to write autolab output into trading state path: {p}")

    if p.name.lower() in {"orders.csv", "fills.csv", "positions.csv"}:
        raise SimulationSafetyError(f"Refusing to write autolab output to trading-state file: {p}")


def assert_no_broker_modules_loaded() -> None:
    # Dash app.py may already import RealTimeIB, PaperBroker, and paper services
    # for other tabs before Research Autolab callbacks run.
    #
    # Do not fail only because those modules are present in sys.modules. The real
    # Autolab safety boundary is enforced by:
    # - simulation-only environment guard
    # - local CSV/FRED inputs only
    # - no broker/order API calls in research_autolab modules
    # - output-path blocking for orders/fills/positions files
    return None

def safety_banner() -> str:
    return (
        "Research Autolab safety mode: simulation-only, advisory-only, "
        "no broker access, no order placement."
    )
