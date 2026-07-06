# Research Analyst name-error hotfix 36f5

Fixes a remaining callback helper-name mismatch in `Live/services/ai/research_analyst_callbacks.py`.

The broken callback called `_enhance_research_analyst_question(...)`, but the available helper is `_enhance_research_analyst_user_prompt(...)`.

This patch replaces the stale call and compiles the callback file.
