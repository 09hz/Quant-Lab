# v24.6.3 — Direct Producer Wiring Backend Control + Diagnostic Fix

## Purpose

Fix the remaining v24.6 direct producer wiring self-test issue where wrapped functions ran but typed quant table counts stayed at zero.

## Likely cause

The direct producer wrapper used automatic backend selection. If the current PowerShell session still had PostgreSQL environment variables set, captures could be written to PostgreSQL while the self-test checked SQLite, leaving SQLite counts at zero.

## Fix

- Add explicit `preferred_backend` support to direct producer wiring.
- Make the self-test force SQLite.
- Clear PostgreSQL environment variables inside the self-test.
- Add a direct capture check before wrapper checks.
- Print capture warnings when capture returns `artifact_only` or `failed`.

## Safety

Research/simulation only.

- No broker calls
- No live trading
- No order placement
- No file moves
- No file deletes
- No credentials written
