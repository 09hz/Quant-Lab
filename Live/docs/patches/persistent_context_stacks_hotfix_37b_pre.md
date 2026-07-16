# Persistent context stacks hotfix 37b-pre

## Purpose

Fix stack behavior before multi-symbol/quant research work.

## Changes

- Newsroom `dcc.Store` components now use session storage.
- Add-to-Brief appends and deduplicates selected items instead of replacing the brief list.
- Strategy Lab AI context attach now appends the current Strategy/Backtest context to the existing attached context.
- Clear Context remains the only Strategy AI action that intentionally clears the attached context stack.

## Safety

- No broker access.
- No order placement.
- No secrets are intentionally stored or exposed; attached context is still passed through the existing redaction helper.
