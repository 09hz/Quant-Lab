# v24.8.1.1 — Quant Dashboard Tab Self-Test Regex Fix

## Purpose

Fix the v24.8.1 self-test failure:

```text
AssertionError
assert len(re.findall(r"BEGIN v24\\.8\\.1 quant dashboard top-level tab", text)) == 1
```

## Cause

The patch itself installed the Quant Dashboard tab block, but the self-test used an over-escaped regex. It looked for literal backslashes instead of the marker text in `Live/app.py`.

## Fix

Replace the fragile regex check with:

```python
text.count("BEGIN v24.8.1 quant dashboard top-level tab") == 1
```

## Safety

Self-test repair only.

- No Data Library edits
- No main app layout changes
- No broker calls
- No live trading
- No order placement
- No inserts, updates, deletes, or file moves
- No credentials written
