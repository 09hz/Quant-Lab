# v22_1_integrate_auto_lab_dash_tab

Adds a top-level `AI Auto Lab` tab to the main Dash app, with dedicated CSS and main-app callbacks that reuse the existing universe and walk-forward runners.

Safety: research/simulation only. No broker calls, no live orders, no PaperBroker calls, no secrets.

Adds:
- Live/ui/auto_lab_ui.py
- Live/services/ai/auto_lab_orchestrator/auto_lab_main_callbacks.py
- Live/services/ai/auto_lab_orchestrator/auto_lab_main_ui_self_test.py
- Live/assets/auto_lab.css

Patches:
- Live/app.py

Old Research Auto Lab is not deleted yet. It remains in place until the new tab is confirmed stable.
