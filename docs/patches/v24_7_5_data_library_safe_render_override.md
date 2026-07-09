# v24.7.5 — Data Library Safe Render Override

## Purpose

Fix the browser-side React error:

```text
Minified React error #31
object with keys {props, type, namespace}
```

This usually means a Dash component object was placed somewhere React expected plain text or a valid child list. After the failed v24.7 Quant Dashboard insertion, the safest recovery is to bypass the damaged Data Library layout builder and replace it with a simple, known-good Data Library recovery view.

## What this patch does

1. Removes v24.7 Quant Dashboard integration fragments from `app.py` and `data_library_ui.py`.
2. Appends a safe override to `data_library_ui.py`.
3. The override replaces detected Data Library builder functions with a simple static Dash layout.
4. The safe layout reads existing catalog SQLite counts directly.
5. It adds a manual recovery note and keeps the original catalog files untouched.
6. It writes a self-test that imports the Data Library UI and calls the replacement builder.

## What this patch does not do

- It does not delete catalog files.
- It does not delete PostgreSQL files.
- It does not move artifacts.
- It does not place trades.
- It does not connect to brokers.
- It does not write credentials.

## Next step after recovery

After the Data tab renders again, v24.7 should be re-integrated as a separate top-level tab or as a route-level view, not by mutating the existing Data Library layout.
