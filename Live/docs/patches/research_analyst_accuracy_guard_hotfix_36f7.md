# Research Analyst accuracy guard hotfix 36f7

Fixes the Research Analyst output-budget checker failure after the recursion hotfix.

Changes:

- Rewrites `_enhance_research_analyst_user_prompt` as a non-recursive helper.
- Restores the explicit series/value accuracy guard required by the checker.
- Instructs the AI not to mix values across CPI, core CPI, PCE, core PCE, FEDFUNDS, sector data, or earnings data.
- Keeps current-fact grounding limited to the Newsroom evidence packet and approved supplemental source candidates.
