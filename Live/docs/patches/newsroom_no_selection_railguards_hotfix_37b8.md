# Newsroom no-selection-railguards hotfix 37b8

Purpose: make Newsroom brief adding user-controlled.

Changes:
- Every visible Newsroom result row becomes selectable.
- Add Selected to Brief appends every matched visible row.
- Duplicate-looking rows are no longer blocked by URL/id/title dedupe.
- The brief preview reports selected, matched, added, unmatched, total, and mode.
- Clear Brief remains the only explicit clearing action.

Safety:
- This does not change broker/order behavior.
- Low-confidence/search/context rows remain labeled through their source metadata and summaries.
- The AI should continue to separate confirmed evidence from context/search pages.
