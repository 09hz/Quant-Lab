# diagnose_bls_sec_fred_context_v18_3

## Purpose

Read-only diagnostic after the BLS + SEC + FRED test.

The test showed:

- BLS evidence reached the Analyst.
- FRED evidence reached the Analyst.
- The displayed Research Brief / Sources panel still contained all six SEC companyfacts rows.
- But the Analyst answer only inventoried one partial SEC row and said the rest of the SEC fields were missing.

This diagnostic checks whether the forced combined evidence context still contains the full SEC table after the BLS patch.

## What it checks

Debug files under:

```text
Live/data/autolab_payload/
```

Specifically:

- `research_analyst_last_sec_context.txt`
- `research_analyst_last_fred_context.txt`
- `research_analyst_last_bls_context.txt`
- `research_analyst_last_combined_context.txt`

It counts:

- SEC table header
- SEC metric rows: revenue, net_income, eps, operating_income, cash, shares
- FRED table header and series rows
- BLS table header and series rows
- metadata-only / official-series rows
- blank/unavailable rows

It also inspects:

```text
Live/services/ai/research_analyst_callbacks.py
```

for the combined evidence variable wiring.

## Files written

```text
diagnostics_bls_sec_fred_context_v18_3.json
docs/patches/diagnose_bls_sec_fred_context_v18_3.md
```

No app code is patched by this diagnostic.

## Next step

Paste the terminal output. The next fix should be based on whether:

1. the SEC table is missing from `research_analyst_last_combined_context.txt`, or
2. the SEC table exists but the prompt instructions let the model trust compact source snippets over the forced evidence table.
