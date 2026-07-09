from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class AdapterResult:
    status: str
    payload: dict[str, Any]
    warnings: list[str]


class BacktestAdapter(Protocol):
    """Future adapter for the real BackTestEngine.

    v24.9.2 only defines the interface. The research loop still uses
    deterministic proxy evaluation until v24.9.3 implements a concrete adapter.
    """

    def run_backtest(self, *, candidate: Any, symbol: str, repo_root: str) -> AdapterResult:
        ...


class AutoLabAdapter(Protocol):
    """Future adapter for Auto Lab candidate generation/mutation."""

    def generate_candidates(self, *, theme: str, symbols: list[str], max_candidates: int, repo_root: str) -> AdapterResult:
        ...


class WalkForwardAdapter(Protocol):
    """Future adapter for real walk-forward validation."""

    def run_walk_forward(self, *, candidate: Any, symbols: list[str], repo_root: str) -> AdapterResult:
        ...


class UniverseAdapter(Protocol):
    """Future adapter for real universe robustness testing."""

    def run_universe_test(self, *, candidate: Any, symbols: list[str], repo_root: str) -> AdapterResult:
        ...


class ProxyBacktestAdapter:
    """Explicit marker for the current v24.9.x deterministic proxy path."""

    name = "proxy_backtest_adapter"
    mode = "simulation_only"

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "mode": self.mode,
            "real_backtest_engine": False,
            "broker_calls": False,
            "order_placement": False,
            "next_adapter": "v24.9.3 Real BackTestEngine Adapter",
        }
