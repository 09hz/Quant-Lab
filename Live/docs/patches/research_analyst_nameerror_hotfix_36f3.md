# Patch 36f3 - Research Analyst callback NameError hotfix

## Problem

After the output-budget patch, the Newsroom **Ask Research Analyst** button fired the Dash callback but failed with:

```text
NameError: name '_enhance_research_analyst_question' is not defined
```

Patch 36f renamed the helper to `_enhance_research_analyst_user_prompt`, but one callback path still called the old helper name.

## Fix

This patch adds a small compatibility wrapper named `_enhance_research_analyst_question(...)` that delegates to `_enhance_research_analyst_user_prompt(...)`.

The wrapper preserves the stronger market-impact prompt behavior and allows older callback code paths to keep working.

## Files

- `Live/services/ai/research_analyst_callbacks.py`
- `Live/scripts/check_research_analyst_nameerror_hotfix.py`
