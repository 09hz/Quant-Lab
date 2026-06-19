# Analytics Workspace Rewrite

Files:

- `tabs_ui.py` -> replace `Live/ui/tabs_ui.py`
- `style.css` -> replace `Live/assets/style.css`
- `callbacks_trade_analytics_replacement.py` -> copy this callback block into `Live/callbacks.py`

## callbacks.py change

1. Delete the old `toggle_trade_analytics_drawer` callback.
2. Replace the old `render_trade_analytics_content(...)` callback with the contents of `callbacks_trade_analytics_replacement.py`.

This moves Trade Analytics from the fixed side drawer into the third Watch workspace tab.

## Test

From the project root:

```bash
python -m py_compile Live/ui/tabs_ui.py
python -m py_compile Live/callbacks.py
python Live/app.py
```
