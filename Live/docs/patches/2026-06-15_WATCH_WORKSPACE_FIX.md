# Watch Workspace Tabs Fix

Files included:

- `Live/ui/tabs_ui.py`
- `Live/assets/style.css`

What changed:

- Removed the duplicated `watch-workspace-tabs` block from `tabs_ui.py`.
- Kept all existing component IDs the same so callbacks continue to work.
- Put Strategy Lab and Paper Trading into one nested Watch workspace tab group.
- Left the Trade Analytics drawer outside the nested tabs so it remains accessible.
- Added CSS overrides for the nested Watch workspace tabs.

After copying into your project, run:

```bash
python -m py_compile Live/ui/tabs_ui.py
python Live/app.py
```
