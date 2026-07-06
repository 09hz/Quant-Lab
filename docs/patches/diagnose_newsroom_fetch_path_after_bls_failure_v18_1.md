# diagnose_newsroom_fetch_path_after_bls_failure_v18_1

## Purpose

Read-only diagnostic after `add_bls_newsroom_evidence_v18.py` failed with:

```text
Could not find _fetch_results in newsroom_callbacks.py
```

The failed patch assumed the Newsroom fetch helper was named `_fetch_results`. This diagnostic finds the real fetch function / insertion point before another patch is made.

## What it checks

- Compiles `Live/services/research/newsroom_callbacks.py`
- Lists function names and line numbers
- Finds references to:
  - `extend_results_with_fred`
  - `extend_results_with_sec_companyfacts`
  - `results =`
  - `return results`
  - `newsroom-fetch`
  - source filter variables
- Shows context windows around the likely insertion points

## Files written

```text
diagnostics_newsroom_fetch_path_v18_1.json
docs/patches/diagnose_newsroom_fetch_path_after_bls_failure_v18_1.md
```

No app code is patched by this diagnostic.

## Next step

Paste the terminal output. The next patch should use the confirmed insertion point instead of assuming `_fetch_results`.
