# fix_sec_tail_guard_authoritative_prompt_v18_5

## Purpose

Fix the case where the combined debug context contains all six SEC rows, but the Analyst still says SEC is missing.

Confirmed from diagnostics / terminal checks:

```text
research_analyst_last_combined_context.txt
FULL CURRENT NEWSROOM SEC COMPANYFACTS TABLE
SEC card count: 6
metric: revenue
metric: net_income
metric: eps
metric: operating_income
metric: cash
metric: shares
```

So the SEC data is present. The failure is likely prompt/context priority or input truncation: the SEC table is at the beginning of the combined evidence packet, while later FRED/BLS sections may be retained more reliably by the LLM call.

## What changed

Patches:

```text
Live/services/ai/research_analyst_callbacks.py
```

### 1. Context tail guard

After the combined SEC/FRED/BLS evidence context is prepended, this patch also appends a compact SEC repeat checkpoint to the end of the evidence context:

```text
SEC AUTHORITATIVE REPEAT CHECKPOINT
```

This makes the SEC rows visible even if earlier prompt/context text is de-prioritized or clipped.

### 2. User prompt tail guard

The prompt override now repeats the SEC table near the end of the user prompt before the user's actual question.

This is intentionally redundant because the bug is not missing data; it is the model failing to respect the SEC table when the combined packet is long.

### 3. Stronger rule text

The prompt now explicitly says:

- If `SEC card count: 6`, the answer must inventory six SEC rows.
- Do not infer SEC absence from the compact Sources Used panel.
- Preserve SEC ticker, metric, value, unit, period_end, filed, form, accession, and concept exactly.

## Files written

```text
docs/patches/fix_sec_tail_guard_authoritative_prompt_v18_5.md
```

## Safety

- No backups are created.
- No broker/order/live trading behavior is added.
- This is evidence prompt/context routing only.
