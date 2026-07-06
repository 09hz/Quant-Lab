# diagnose_auto_lab_capital_callback_v22_2_3

## Purpose

Read-only diagnostic for the AI Auto Lab capital summary panel.

This verifies:

- The capital input component IDs exist in the layout.
- `capital_controls.normalize_capital()` and `capital_markdown()` produce dynamic values.
- `auto_lab_main_callbacks.py` defines/registers a dedicated capital summary callback.
- `Live/app.py` imports/builds the AI Auto Lab tab.
- `Live/app.py` registers `register_auto_lab_main_callbacks(app)`.
- The imported Dash app callback map contains `main-autolab-capital-summary.children`.
- The callback inputs are the expected capital fields.
- Whether there are duplicate/missing output registrations.

## Safety

Read-only diagnostic for code/runtime inspection.

No backups.
No app patching.
No broker calls.
No live orders.
No PaperBroker calls.
