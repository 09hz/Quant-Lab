# Patch 37d - Hydrate approved FRED recommendations

This patch converts approved FRED recommendation cards into structured evidence cards.

## Behavior

- FRED recommendation approval attempts to fetch public FRED CSV observations.
- Hydrated FRED cards include latest value, prior value, 1/3/6-period changes, direction labels, and metadata trend payload.
- Non-FRED recommendation approvals remain discovery-only cards.
- Hydration failures do not crash Dash; they append a warning card and report the failure count.

## Safety

The workflow remains user-approved and research-only. The app does not place orders or use broker access.
