# Research Analyst supplemental_count signature hotfix 36f12

Fixes a callback error where `_enhance_research_analyst_user_prompt(...)`
was called with `supplemental_count=...` but the helper signature did not
accept that keyword argument.

## Changes

- Adds `output_style="concise"` and `supplemental_count=0` defaults to the helper.
- Normalizes the supplemental count safely.
- Adds a prompt instruction explaining that supplemental Newsroom candidates
  are context and should be labeled as lower-confidence unless confirmed.
- Updates the second helper call to pass `output_style=output_style`.
- Adds a checker for the signature/call wiring.
