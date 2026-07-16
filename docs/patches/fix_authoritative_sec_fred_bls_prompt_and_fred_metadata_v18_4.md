# fix_authoritative_sec_fred_bls_prompt_and_fred_metadata_v18_4

## Purpose

Fix the BLS + SEC + FRED combined test result.

The diagnostic confirmed:

- `research_analyst_last_combined_context.txt` contains all three headers:
  - `FULL CURRENT NEWSROOM SEC COMPANYFACTS TABLE`
  - `FULL CURRENT NEWSROOM FRED EVIDENCE TABLE`
  - `FULL CURRENT NEWSROOM BLS EVIDENCE TABLE`
- The combined context contains all six SEC metrics:
  - revenue
  - net_income
  - eps
  - operating_income
  - cash
  - shares
- The Analyst still claimed SEC fields were missing, so the issue was prompt priority / source-conflict handling, not missing SEC data.
- FRED `official-series` metadata cards were being converted into blank numeric rows for PAYEMS/UNRATE.

## What changed

### 1. Stronger authoritative evidence instructions

Patches:

```text
Live/services/ai/research_analyst_callbacks.py
```

The user prompt override now tells the Analyst:

- the forced tables are the authoritative evidence packet,
- compact source lists are secondary,
- if the SEC table says `SEC card count: 6`, every SEC row must be inventoried,
- do not say SEC is missing when the table contains all SEC fields,
- metadata-only FRED links are not numeric rows.

### 2. FRED metadata-only filtering

Replaces:

```python
_fred_newsroom_evidence_markdown(...)
```

The new helper separates:

```text
FRED numeric data rows
FRED metadata-only source links
```

This prevents `official-series` cards like PAYEMS/UNRATE from being reported as blank numeric data rows when no latest/prior values were fetched.

### 3. Debug output

After the next Ask, check:

```text
Live/data/autolab_payload/research_analyst_last_fred_context.txt
Live/data/autolab_payload/research_analyst_last_combined_context.txt
```

Expected:

```text
FRED numeric data card count: 4
FRED METADATA-ONLY SOURCE LINKS
```

If official-series links are present.

## Files written

This patch writes its notes to:

```text
docs/patches/fix_authoritative_sec_fred_bls_prompt_and_fred_metadata_v18_4.md
```

## Safety

- No backups are created.
- No live trading, broker, order, or position-sizing behavior is added.
- This is evidence handling and prompt-routing only.
