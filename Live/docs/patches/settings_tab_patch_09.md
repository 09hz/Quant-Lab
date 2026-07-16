# Patch 09 — Settings Tab Foundation

## Summary

This patch converts the old **Charts** tab into a read-only **Settings** tab.

The function name `build_charts_tab(...)` is intentionally kept for compatibility so existing imports and callback registration do not break immediately.

## What changed

- Renames the visible tab label from `Charts` to `Settings`.
- Replaces the visible old Charts panel with a Settings panel.
- Shows provider/configuration values from environment variables.
- Shows a lightweight local cache summary.
- Adds useful command examples.
- Masks secrets such as `TRADIER_ACCESS_TOKEN`.
- Keeps hidden legacy Charts components so old callbacks referencing `charts-*` IDs do not break.

## Files changed

- `Live/ui/tabs_ui.py`
- `Live/app.py` if it contains the tab label
- `Live/assets/zz_settings_tab.css`
- `Live/docs/patches/settings_tab_patch_09.md`

## Security notes

This Settings tab is read-only.

It does not:

- Save `.env` files.
- Store secrets in browser storage.
- Place orders.
- Change broker/provider state at runtime.
- Expose API tokens.

Secrets must continue to be set outside the app through environment variables or a local `.env` file that is not committed to Git.

## Next possible patch

Patch 09b can add a Settings diagnostics button that calls the existing provider health code and displays the result in the Settings tab.
