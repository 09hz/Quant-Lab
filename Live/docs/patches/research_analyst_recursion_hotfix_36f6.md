# Research Analyst recursion hotfix 36f6

Fixes a callback crash introduced during the Research Analyst output-budget hotfix chain.

## Problem

`_enhance_research_analyst_user_prompt(...)` recursively called itself, causing:

```text
RecursionError: maximum recursion depth exceeded
```

when the Newsroom **Ask Research Analyst** button was pressed.

## Change

- Replaces the recursive helper with a deterministic prompt-expansion helper.
- Keeps the Research Analyst grounded in the Newsroom evidence packet and approved supplemental source candidates.
- Preserves the improved answer shape:
  - executive read
  - highlights
  - broad market impact
  - tech impact
  - manufacturing impact
  - correlation/transmission path
  - what would invalidate the view
  - sources used and remaining gaps
- Adds `Live/scripts/check_research_analyst_recursion_hotfix.py`.

No backup files are created.
