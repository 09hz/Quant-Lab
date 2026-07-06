# Hotfix 37c3 — Strict Source Coverage for Evidence Recommendations

The first recommendation queue could mark buckets as present when the brief contained an AI/playbook gap list that mentioned series names like DGS10, VIXCLS, PAYEMS, or UMCSENT.

This hotfix changes coverage detection so that:
- approved/source-like cards count as evidence,
- AI gap lists, quant playbooks, hypothesis text, and insufficient-evidence summaries do not count,
- approved recommendation cards count after the user approves them,
- the queue will still recommend missing source candidates when only narrative gap text is present.

No backup files are created.
