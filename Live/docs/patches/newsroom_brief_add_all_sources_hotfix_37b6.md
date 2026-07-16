# Patch 37b6 - Newsroom add-all visible source mode

This hotfix changes Newsroom brief selection to favor user choice:

- Every visible Newsroom result row is selectable for the brief.
- Low-confidence/context/search rows are labeled with caution instead of silently blocked.
- Checklist values use unique visible-row selection ids.
- Brief dedupe uses a stable URL/source/title key instead of raw result ids.
- Add Selected appends a visible `Last Add Action` summary to the brief preview:
  - selected rows
  - added rows
  - skipped duplicates
  - unmatched selections
  - brief total

The brief remains advisory-only AI context. This does not add broker access, order
placement, or hidden browsing.
