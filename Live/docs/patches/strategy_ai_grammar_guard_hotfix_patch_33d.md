
# Patch 33d - Strategy AI Grammar Guard Prompt-Path Hotfix

Patch 33c added the grammar guard/checker, but on some trees the applier did
not find the exact `build_prompt` try block in `advisor_callbacks.py`.

This hotfix patches the prompt path defensively by locating the actual
`built_prompt, built_context = build_prompt(...)` call and inserting
`augment_strategy_ai_prompt(...)` immediately before it.

The Strategy AI should now receive the parser contract on each request:
- no imports
- no pandas/numpy
- no functions
- no `>=` or `<=`
- no inline math inside boolean comparisons
- no short logic unless explicitly supported
