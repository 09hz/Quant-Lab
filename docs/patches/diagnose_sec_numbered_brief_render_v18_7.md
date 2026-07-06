# diagnose_sec_numbered_brief_render_v18_7

## Purpose

Read-only diagnostic after `normalize_sec_brief_numbered_rows_v18_6.py`.

The screenshot still showed SEC cards rendered as:

```text
### SEC companyfacts official-data card
```

instead of numbered rows like:

```text
### 5. SEC companyfacts: AMD cash
```

This diagnostic checks the exact current functions/calls before another patch.

## What it checks

File:

```text
Live/services/research/newsroom_callbacks.py
```

Checks:

- whether `_sec_companyfacts_card_markdown` signature includes `index`
- every occurrence of `SEC companyfacts official-data card`
- every call to `_sec_companyfacts_card_markdown(...)`
- the full `_sec_companyfacts_card_markdown` function window
- the full `_brief_markdown` function window
- whether `_brief_markdown` passes `idx`

## Files written

```text
diagnostics_sec_numbered_brief_render_v18_7.json
docs/patches/diagnose_sec_numbered_brief_render_v18_7.md
```

No app code is patched.
