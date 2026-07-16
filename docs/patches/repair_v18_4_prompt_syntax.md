# repair_v18_4_prompt_syntax

## Purpose

Repair a syntax error introduced by `fix_authoritative_sec_fred_bls_prompt_and_fred_metadata_v18_4.py`.

The failed line looked like this:

```text
+ "5. ...\\n"\n        + "6. ...\\n\\n"\n                    + analyst_user_prompt
```

The literal `\n` text was accidentally inserted into Python source instead of real newlines.

## What this repair changes

Patches:

```text
Live/services/ai/research_analyst_callbacks.py
```

It replaces only the user-prompt override block between:

```python
# v14 combined SEC/FRED table user-prompt override
# end v14 combined SEC/FRED table user-prompt override
```

with a clean valid Python block.

## Keeps the intended v18.4 behavior

The repaired block still says:

- forced Newsroom evidence tables are authoritative,
- compact source lists are secondary,
- SEC/FRED/BLS rows should all be inventoried,
- FRED metadata-only links are source leads, not blank numeric rows,
- all six SEC fields should be preserved when SEC rows are present.

## Files written

```text
docs/patches/repair_v18_4_prompt_syntax.md
```

## Safety

- No backups are created.
- No live trading, broker, order, or position-sizing behavior is added.
- This is syntax repair and prompt-routing text only.
