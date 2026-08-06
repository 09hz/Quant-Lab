from __future__ import annotations

from pathlib import Path
import sys


def _bootstrap_import_path() -> Path:
    here = Path(__file__).resolve()
    live_root = here.parents[3]
    repo_root = here.parents[4]
    for path in (str(live_root), str(repo_root)):
        if path not in sys.path:
            sys.path.insert(0, path)
    return live_root


def main() -> int:
    live_root = _bootstrap_import_path()

    from services.ai.auto_lab_orchestrator.seed_library import discover_strategy_seed_candidates, built_in_seed_candidates
    from services.ai.auto_lab_orchestrator.templates import find_strategy_example_files, _looks_like_strategy_script
    from services.ai.auto_lab_orchestrator.mutator import generate_mutations_for_parents, preview_parameter_mutations
    from services.ai.auto_lab_orchestrator.sample_data import make_sample_bars_dataframe
    from core.StrategyEngine import StrategyEngine

    symbol = "AMD"
    built_ins = built_in_seed_candidates(symbol=symbol)
    example_files = find_strategy_example_files(live_root, limit=20)
    seeds = discover_strategy_seed_candidates(live_root=live_root, symbol=symbol, max_examples=12, include_built_ins=True)

    assert built_ins, "Expected built-in seed candidates"
    assert seeds, "Expected at least built-in seeds"
    assert all(seed.script for seed in seeds), "Every seed should have a script"
    expected_families = {
        "crossover",
        "rsi_mean_reversion",
        "bollinger_mean_reversion",
        "roc_momentum",
        "adx_trend",
        "supertrend",
    }
    assert expected_families.issubset({seed.family for seed in built_ins})

    bars = make_sample_bars_dataframe(symbol=symbol, days=260)
    engine = StrategyEngine()
    for seed in seeds:
        result = engine.run(seed.script, bars)
        assert not result.errors, f"Seed {seed.candidate_id} failed: {result.errors}"

    bad_ids = [seed.candidate_id for seed in seeds if any(token in seed.candidate_id.lower() for token in ("requirements", "changelog", "language", "readme"))]
    assert not bad_ids, f"Bad doc-like candidates leaked into seed list: {bad_ids}"

    mutations = preview_parameter_mutations(built_ins[0], max_mutations=4)
    assert mutations, "Expected mutation previews"
    assert any("structural" in mutation.tags for mutation in mutations)

    diverse_mutations = generate_mutations_for_parents(
        built_ins,
        max_mutations_per_parent=3,
        max_total=len(built_ins),
    )
    mutation_families = {mutation.family for mutation in diverse_mutations}
    assert len(mutation_families) >= min(5, len(built_ins)), mutation_families

    print("AI Auto Lab seed discovery self-test: PASS")
    print(f"Live root: {live_root}")
    print(f"Example files found: {len(example_files)}")
    for path in example_files[:10]:
        print(f"- example_file: {path}")
    print(f"Seeds discovered: {len(seeds)}")
    for seed in seeds[:15]:
        print(f"- seed: {seed.candidate_id} source={seed.source}")
    print(f"Mutation previews from {built_ins[0].candidate_id}: {len(mutations)}")
    for mutation in mutations:
        print(f"- mutation: {mutation.candidate_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
