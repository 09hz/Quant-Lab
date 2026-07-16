# v24.7.6 — Force Safe Data Tab in `app.py`

## Purpose

Fix persistent browser-side React error #31 on the Data tab:

```text
Minified React error #31
object with keys {props, type, namespace}
```

This means the Data tab layout is still rendering a Dash component object in a place where React expects a plain value. Previous recovery patches repaired syntax and disabled the Quant Dashboard wrapper, but the Data tab path is still using a damaged layout.

## Fix

This patch bypasses the damaged Data Library layout at the top-level Dash tab.

It:

1. Adds `_v24_7_6_build_safe_data_library_tab()` directly to `Live/app.py`.
2. Replaces the `dcc.Tab(...)` block whose label contains `Data Library` / `Data` or whose block calls `build_data_library...`.
3. The replacement tab keeps the same tab `value` when it can detect it.
4. The replacement children use only a simple safe Dash layout that reads catalog SQLite counts.
5. Removes lingering v24.7 Quant Dashboard callback/import fragments from `app.py`.
6. Compiles `app.py`.
7. Adds a self-test that verifies `app.py` points the Data tab to the safe builder.

## Result

The Data tab should render a simple recovery view instead of the full Data Library UI. This is intentional. Once the app is stable again, the full Data Library and Quant Dashboard should be re-integrated as a clean separate top-level tab or route, not by mutating the old Data Library layout.

## Safety

Read-only UI recovery.

- No broker calls
- No live trading
- No order placement
- No file moves
- No file deletes
- No credentials written
