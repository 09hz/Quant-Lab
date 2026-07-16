# Patch 31b — Newsroom Result Hygiene

## Goal

Reduce clutter and avoid sending weak research links to AI.

This patch keeps the Newsroom lightweight. It does **not** add macro charts. Official sources like FRED already host full charts and methodology pages, so the app should focus on:

- finding relevant official sources,
- showing small structured summaries when available,
- hiding page-not-found results,
- downgrading generic search pages,
- building a cleaner research brief.

## Behavior

Result cards are classified as:

- `structured` — fetched structured data, usually selectable
- `direct` — direct official page/data page, selectable if the existing source logic allows it
- `manual_search` — generic source search page, visible but not selectable for the brief
- `hidden` — broken/page-not-found/invalid result, hidden from the normal list

## Why search pages are not selectable

Search pages can help a human continue research, but they are weak evidence for the AI. They usually do not prove a fact by themselves. The AI should receive selected direct/structured results instead.

## Test

```powershell
python .\Live\scripts\check_newsroom_result_hygiene.py
python .\Live\scripts\check_newsroom_result_hygiene.py --json
```

Then run the app and search Newsroom for:

```text
inflation rate
federal debt deficit
MSFT 10-K inflation
```

## Notes

No API keys are added.
No backup files are created.
No charts are added.
