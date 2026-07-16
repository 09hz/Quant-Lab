from __future__ import annotations

from .models import StrategyCandidate
import re


def _candidate_copy(
    candidate: StrategyCandidate,
    suffix: str,
    script: str,
    parameters: dict,
    mutation: dict,
) -> StrategyCandidate:
    parent_id = candidate.candidate_id
    clean_suffix = re.sub(r"[^a-zA-Z0-9_]+", "_", suffix).strip("_")[:40]
    return StrategyCandidate(
        candidate_id=f"{parent_id}_{clean_suffix}"[:120],
        name=f"{candidate.name} {clean_suffix}".replace("_", " ").strip(),
        family=candidate.family,
        script=script,
        parameters=parameters,
        symbols=list(candidate.symbols),
        tags=sorted(set(list(candidate.tags) + ["mutation", "simulation-only"])),
        source=f"mutation_of:{parent_id}",
        notes=(
            f"Deterministic mutation of {parent_id}. "
            f"Mutation={mutation}. Research/simulation only."
        ),
    )


def _dedupe(candidates: list[StrategyCandidate]) -> list[StrategyCandidate]:
    seen: set[tuple[str, str]] = set()
    out: list[StrategyCandidate] = []
    for candidate in candidates:
        key = (candidate.candidate_id, (candidate.script or "").strip())
        if key in seen:
            continue
        seen.add(key)
        out.append(candidate)
    return out


def _number_variants(value: int, *, min_value: int = 2, max_value: int = 250) -> list[int]:
    candidates = [
        value - 10,
        value - 5,
        value - 3,
        value + 3,
        value + 5,
        value + 10,
    ]
    return [v for v in candidates if min_value <= v <= max_value and v != value]


def _threshold_variants(value: int, *, low: int, high: int) -> list[int]:
    candidates = [value - 10, value - 5, value + 5, value + 10]
    return [v for v in candidates if low <= v <= high and v != value]


def _replace_span(text: str, start: int, end: int, replacement: str) -> str:
    return text[:start] + replacement + text[end:]


def _mutate_ma_calls(candidate: StrategyCandidate, max_count: int) -> list[StrategyCandidate]:
    script = candidate.script or ""
    results: list[StrategyCandidate] = []
    pattern = re.compile(r"\b(ema|sma)\(\s*close\s*,\s*(\d+)\s*\)", re.IGNORECASE)
    matches = list(pattern.finditer(script))

    for call_index, match in enumerate(matches):
        if len(results) >= max_count:
            break
        fn = match.group(1)
        current = int(match.group(2))
        for new_value in _number_variants(current):
            if len(results) >= max_count:
                break
            replacement = f"{fn}(close, {new_value})"
            new_script = _replace_span(script, match.start(), match.end(), replacement)
            params = dict(candidate.parameters or {})
            key = "fast" if call_index == 0 else ("slow" if call_index == 1 else f"ma_{call_index+1}")
            params[key] = new_value
            mutation = {"type": "moving_average_window", "call_index": call_index, "from": current, "to": new_value}
            suffix = f"{key}_{current}_to_{new_value}"
            results.append(_candidate_copy(candidate, suffix, new_script, params, mutation))
    return results


def _mutate_rsi_length(candidate: StrategyCandidate, max_count: int) -> list[StrategyCandidate]:
    script = candidate.script or ""
    results: list[StrategyCandidate] = []
    pattern = re.compile(r"\brsi\(\s*close\s*,\s*(\d+)\s*\)", re.IGNORECASE)
    match = pattern.search(script)
    if not match:
        return results

    current = int(match.group(1))
    for new_value in _number_variants(current, min_value=2, max_value=60):
        if len(results) >= max_count:
            break
        replacement = f"rsi(close, {new_value})"
        new_script = _replace_span(script, match.start(), match.end(), replacement)
        params = dict(candidate.parameters or {})
        params["rsi_length"] = new_value
        mutation = {"type": "rsi_length", "from": current, "to": new_value}
        results.append(_candidate_copy(candidate, f"rsi_{current}_to_{new_value}", new_script, params, mutation))
    return results


def _mutate_thresholds(candidate: StrategyCandidate, max_count: int) -> list[StrategyCandidate]:
    script = candidate.script or ""
    results: list[StrategyCandidate] = []

    buy_pattern = re.compile(r"((?:buy\s+when|buy\s*=).*?<\s*)(\d+)", re.IGNORECASE)
    buy_match = buy_pattern.search(script)
    if buy_match:
        current = int(buy_match.group(2))
        for new_value in _threshold_variants(current, low=5, high=60):
            if len(results) >= max_count:
                break
            new_script = _replace_span(script, buy_match.start(2), buy_match.end(2), str(new_value))
            params = dict(candidate.parameters or {})
            params["buy_threshold"] = new_value
            mutation = {"type": "buy_threshold", "from": current, "to": new_value}
            results.append(_candidate_copy(candidate, f"buy_thr_{current}_to_{new_value}", new_script, params, mutation))

    sell_pattern = re.compile(r"((?:sell\s+when|sell\s*=).*?>\s*)(\d+)", re.IGNORECASE)
    sell_match = sell_pattern.search(script)
    if sell_match:
        current = int(sell_match.group(2))
        for new_value in _threshold_variants(current, low=40, high=95):
            if len(results) >= max_count:
                break
            new_script = _replace_span(script, sell_match.start(2), sell_match.end(2), str(new_value))
            params = dict(candidate.parameters or {})
            params["sell_threshold"] = new_value
            mutation = {"type": "sell_threshold", "from": current, "to": new_value}
            results.append(_candidate_copy(candidate, f"sell_thr_{current}_to_{new_value}", new_script, params, mutation))

    return results


def _mutate_quantity(candidate: StrategyCandidate, max_count: int) -> list[StrategyCandidate]:
    """Available but intentionally disabled by default in v21.3."""
    current = int(float((candidate.parameters or {}).get("quantity", 10)))
    variants = [max(1, current // 2), current * 2]
    results: list[StrategyCandidate] = []
    for new_value in variants:
        if len(results) >= max_count or new_value == current:
            continue
        params = dict(candidate.parameters or {})
        params["quantity"] = new_value
        mutation = {"type": "quantity", "from": current, "to": new_value}
        results.append(_candidate_copy(candidate, f"qty_{current}_to_{new_value}", candidate.script, params, mutation))
    return results


def preview_parameter_mutations(
    candidate: StrategyCandidate,
    max_mutations: int = 6,
    mutate_quantity: bool = False,
) -> list[StrategyCandidate]:
    """
    Generate safe deterministic parameter mutations for a Strategy Lab candidate.

    v21.3 uses signal-logic mutations only by default. Quantity is intentionally
    fixed for cleaner signal testing.
    """
    if not candidate.script:
        return []

    results: list[StrategyCandidate] = []
    for generator in (_mutate_ma_calls, _mutate_rsi_length, _mutate_thresholds):
        if len(results) >= max_mutations:
            break
        results.extend(generator(candidate, max_mutations - len(results)))

    if mutate_quantity and len(results) < max_mutations:
        results.extend(_mutate_quantity(candidate, max_mutations - len(results)))

    return _dedupe(results)[:max_mutations]


def generate_mutations_for_parents(
    parents: list[StrategyCandidate],
    max_mutations_per_parent: int = 4,
    max_total: int = 20,
    mutate_quantity: bool = False,
) -> list[StrategyCandidate]:
    mutations: list[StrategyCandidate] = []
    seen_scripts: set[str] = set()

    for parent in parents:
        if len(mutations) >= max_total:
            break
        parent_mutations = preview_parameter_mutations(
            parent,
            max_mutations=max_mutations_per_parent,
            mutate_quantity=mutate_quantity,
        )
        for mutation in parent_mutations:
            if len(mutations) >= max_total:
                break
            script_key = (mutation.script or "").strip()
            if not script_key or script_key in seen_scripts:
                continue
            seen_scripts.add(script_key)
            mutations.append(mutation)
    return mutations
