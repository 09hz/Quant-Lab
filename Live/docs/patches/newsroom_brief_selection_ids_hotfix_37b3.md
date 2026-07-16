# Newsroom brief selection IDs hotfix 37b3

## Purpose

Fixes a Newsroom brief issue where selecting several visible results could add fewer items than selected.

## Root cause

Dash checklist option values were based on the raw result `id`. Some source builders can reuse the same raw id across rows or searches. When that happens, the checklist selection values collapse, and the add callback cannot distinguish all selected rows.

## Behavior after patch

- Every visible Newsroom result row gets a unique `brief_selection_id`.
- The brief still dedupes true duplicate sources using a stable source key.
- The Add Selected to Brief button appends distinct selected rows.
- Clear Brief remains the only explicit clear action.

## Safety

This is UI/store behavior only. It does not add broker access, order placement, or unrestricted browsing.
