# Patch 37e4 — Research Analyst approved-brief-only manifest and professional tone

This patch tightens the Research Analyst path after hydrated FRED cards are correctly detected.

## Changes

- Adds approved Newsroom brief-only detection.
- Suppresses auto macro anchors and supplemental Newsroom candidates when the user asks to audit the approved Newsroom brief only.
- Repeats the Approved Hydrated FRED Official Data Cards manifest in the user prompt as well as the context.
- Adds professional no-emoji/no-decorative-symbol instructions.
- Adds a checker script.

## Validation

```powershell
python -m py_compile .\Live\services\ai\research_analyst_callbacks.py
python .\Live\scripts\check_research_analyst_brief_only_manifest_noemoji.py
```
