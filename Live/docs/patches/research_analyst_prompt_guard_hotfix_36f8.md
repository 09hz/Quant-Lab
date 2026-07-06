# Research Analyst prompt guard hotfix 36f8

Rewrites the Research Analyst prompt-enhancement helper as a non-recursive function and restores the required market-impact sections.

Restored guardrails include:

- Executive read.
- Market, tech, and manufacturing impact.
- Current-quarter bullish/bearish/mixed read.
- Correlation/transmission path.
- Series/value accuracy guard.
- Final read instruction to reduce truncated answers.

This patch does not enable unrestricted browsing. Answers remain grounded in the Newsroom evidence packet and approved supplemental source candidates.
