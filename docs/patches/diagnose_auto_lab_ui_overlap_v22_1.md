# diagnose_auto_lab_ui_overlap_v22_1

Read-only diagnostic for integrating the new AI Auto Lab tab into the main Dash app.

It inspects:
- Live/app.py
- Live/callbacks.py
- Live/ui/
- Live/assets/
- old Research Auto Lab files
- new Auto Lab orchestrator/UI files
- tab labels/values
- callback IDs
- imports
- CSS overlap

It writes:
- Live/data/diagnostics/diagnose_auto_lab_ui_overlap_v22_1.json
- Live/data/diagnostics/diagnose_auto_lab_ui_overlap_v22_1.md
- docs/patches/diagnose_auto_lab_ui_overlap_v22_1.md

Safety:
- Read-only for app code.
- No backups.
- No broker calls.
- No live orders.
