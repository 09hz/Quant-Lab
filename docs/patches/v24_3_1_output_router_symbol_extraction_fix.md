# v24.3.1 — Output Router Symbol Extraction Fix

## Purpose

Fix the v24.3 self-test failure where filenames using underscores, such as:

```text
autolab_NVDA_result.json
```

did not extract `NVDA` as the symbol.

## Error fixed

```text
AssertionError: None
```

## Cause

The router used a word-boundary regex. In Python regular expressions, underscores count as word characters, so `NVDA` inside `autolab_NVDA_result` was not treated as a separate word.

## Fix

Replace symbol extraction with tokenization that splits on underscores, dashes, dots, spaces, and other separators.

## Safety

Research/simulation only.

- No broker calls
- No live trading
- No order placement
- No file moves
- No file deletes
- No credentials written
