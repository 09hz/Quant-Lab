from __future__ import annotations

from pathlib import Path

from .models import StrategyCandidate
from .templates import load_strategy_example_candidates


def built_in_seed_candidates(symbol: str = "AMD") -> list[StrategyCandidate]:
    """
    Built-in seed candidates that are closer to the current StrategyEngine grammar
    than the early generic v21.0 toy templates.

    These are still only seeds. The core smoke test determines what actually
    passes the current engine.
    """
    return [
        StrategyCandidate(
            candidate_id="seed_boolean_crossover",
            name="Boolean Crossover Seed",
            family="crossover",
            script="\n".join(
                [
                    "fast = ema(close, 12)",
                    "slow = ema(close, 26)",
                    "bullCross = crossover(fast, slow)",
                    "bearCross = crossunder(fast, slow)",
                    "buy when bullCross",
                    "sell when bearCross",
                ]
            ),
            parameters={"quantity": 10, "fast": 12, "slow": 26},
            symbols=[symbol],
            tags=["seed", "crossover", "simulation-only"],
            source="built_in_seed_library",
            notes="Cleaned boolean crossover seed for the current Strategy Lab grammar.",
        ),
        StrategyCandidate(
            candidate_id="seed_ema_crossover",
            name="EMA Crossover Seed",
            family="ema_crossover",
            script="\n".join(
                [
                    "fast = ema(close, 9)",
                    "slow = ema(close, 21)",
                    "buy when crossover(fast, slow)",
                    "sell when crossunder(fast, slow)",
                ]
            ),
            parameters={"quantity": 10, "fast": 9, "slow": 21},
            symbols=[symbol],
            tags=["seed", "ema", "crossover", "simulation-only"],
            source="built_in_seed_library",
            notes="Cleaned EMA crossover seed.",
        ),
        StrategyCandidate(
            candidate_id="seed_rsi_mean_reversion",
            name="RSI Mean Reversion Seed",
            family="rsi_mean_reversion",
            script="\n".join(
                [
                    "r = rsi(close, 14)",
                    "buy when r < 35",
                    "sell when r > 65",
                ]
            ),
            parameters={"quantity": 10, "rsi_length": 14, "buy_threshold": 35, "sell_threshold": 65},
            symbols=[symbol],
            tags=["seed", "rsi", "mean-reversion", "simulation-only"],
            source="built_in_seed_library",
            notes="Cleaned RSI mean-reversion seed.",
        ),
    ]


def discover_strategy_seed_candidates(
    live_root: Path,
    symbol: str = "AMD",
    max_examples: int = 12,
    include_built_ins: bool = True,
) -> list[StrategyCandidate]:
    """
    Discover strategy seeds from strict example folders plus built-ins.

    Order matters:
    1. Real examples from the repo
    2. Built-in cleaned seeds
    """
    seeds: list[StrategyCandidate] = []
    seeds.extend(load_strategy_example_candidates(live_root=live_root, symbol=symbol, limit=max_examples))
    if include_built_ins:
        seeds.extend(built_in_seed_candidates(symbol=symbol))

    # De-dupe by candidate_id while preserving order.
    seen: set[str] = set()
    deduped: list[StrategyCandidate] = []
    for seed in seeds:
        key = seed.candidate_id
        if key in seen:
            continue
        seen.add(key)
        deduped.append(seed)
    return deduped
