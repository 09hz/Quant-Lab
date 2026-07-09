from __future__ import annotations

from hashlib import sha256
from typing import Any

from .models import ResearchLoopConfig, StrategyCandidate


FAMILIES = [
    {
        "family": "momentum_breakout",
        "label": "Momentum Breakout",
        "hypothesis": "Strong semiconductor leadership can continue after price/volume confirmation.",
        "base": {"lookback": 20, "entry_z": 1.2, "exit_z": 0.2, "atr_stop": 2.0, "volume_filter": True},
    },
    {
        "family": "trend_pullback",
        "label": "Trend Pullback",
        "hypothesis": "High-quality trend names may rebound after controlled pullbacks above a long moving average.",
        "base": {"fast_ma": 20, "slow_ma": 100, "pullback_pct": 0.04, "atr_stop": 2.4, "rsi_floor": 42},
    },
    {
        "family": "volatility_compression",
        "label": "Volatility Compression",
        "hypothesis": "Compression followed by expansion may identify renewed institutional demand.",
        "base": {"compression_window": 15, "breakout_window": 30, "atr_quantile": 0.35, "volume_filter": True},
    },
    {
        "family": "mean_reversion_guarded",
        "label": "Guarded Mean Reversion",
        "hypothesis": "Oversold pullbacks can work when filtered by trend and volatility quality.",
        "base": {"rsi_period": 14, "rsi_entry": 34, "rsi_exit": 52, "trend_filter": True, "max_hold_days": 8},
    },
    {
        "family": "relative_strength_rotation",
        "label": "Relative Strength Rotation",
        "hypothesis": "Capital may rotate toward stronger names within the same semiconductor theme.",
        "base": {"rank_window": 30, "top_n": 2, "rebalance_days": 5, "risk_weighted": True},
    },
]


def _stable_int(*parts: Any) -> int:
    text = "|".join(str(part) for part in parts)
    return int(sha256(text.encode("utf-8")).hexdigest()[:12], 16)


def _variant_parameters(base: dict[str, Any], *, seed: str, family: str, index: int) -> dict[str, Any]:
    params = dict(base)
    stable = _stable_int(seed, family, index)

    for key, value in list(params.items()):
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            shift = (stable % 5) - 2
            params[key] = max(1, int(value + shift))
        elif isinstance(value, float):
            factor = 0.85 + ((stable % 31) / 100.0)
            params[key] = round(float(value) * factor, 4)

    params["variant"] = index
    params["simulation_only"] = True
    return params


def generate_strategy_candidates(config: ResearchLoopConfig) -> list[StrategyCandidate]:
    symbols = config.normalized_symbols()
    max_candidates = max(1, int(config.max_candidates or 1))
    candidates: list[StrategyCandidate] = []

    idx = 0
    while len(candidates) < max_candidates:
        spec = FAMILIES[idx % len(FAMILIES)]
        variant = idx // len(FAMILIES)
        family = spec["family"]
        params = _variant_parameters(spec["base"], seed=config.seed, family=family, index=variant)
        theme_token = "".join(ch for ch in config.theme.title() if ch.isalnum())[:32] or "Research"

        candidates.append(
            StrategyCandidate(
                candidate_id=f"cand_{theme_token}_{family}_{variant}",
                strategy_name=f"{spec['label']} v{variant + 1}",
                strategy_family=family,
                hypothesis=spec["hypothesis"],
                symbols=symbols,
                timeframe=config.timeframe,
                parameters=params,
            )
        )
        idx += 1

    return candidates
