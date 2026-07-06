# Patch 37c2 - Research Evidence Recommendation Queue checker hotfix

This hotfix fixes a checker/string-marker mismatch after Patch 37c.

## Why

Patch 37c added the Research Evidence Recommendation Queue, but the checker looked for the exact text `approved recommendation`.
Some callback text used plural wording or UI wording instead.

## What changed

- Added a harmless marker comment in `Live/services/research/newsroom_callbacks.py`.
- Made `Live/scripts/check_research_evidence_recommendation_queue.py` accept the exact marker or plural wording.

## Runtime behavior

No runtime behavior changes. Approved recommendations should still be reviewed by the user before being appended to the Newsroom brief.
