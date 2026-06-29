# Research Analyst supplemental checker path hotfix 36f13

This hotfix rewrites `Live/scripts/check_research_analyst_supplemental_kwarg_hotfix.py`
so it resolves paths from the `Live/scripts` directory correctly.

It validates that:

- `Live/services/ai/research_analyst_callbacks.py` compiles.
- `_enhance_research_analyst_user_prompt(...)` accepts `supplemental_count`.
- The Research Analyst callback passes `supplemental_count=len(supplemental_items)`.
- The helper is non-recursive.
- The required Research Analyst prompt guardrails remain present.

No backup files are created.
