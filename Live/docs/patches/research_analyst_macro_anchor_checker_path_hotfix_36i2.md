# Research Analyst macro anchor checker path hotfix 36i2

Fixes the macro anchor checker import path so it can import `services.*` when run from the repository root.

The app code is not changed by this hotfix. It only updates:

- `Live/scripts/check_research_analyst_macro_anchor_trends.py`

Reason:

- The checker was importing `services.research...` without adding the `Live/` directory to `sys.path`.
- Running the checker from the repository root therefore raised `ModuleNotFoundError: No module named 'services'`.
