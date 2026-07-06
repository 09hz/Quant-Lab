# add_bls_newsroom_evidence_v18_2

## Purpose

Corrected BLS patch after v18 failed because it assumed `newsroom_callbacks.py` used `_fetch_results`.

The confirmed function name is:

```text
_build_results(topic, sources)
```

## Confirmed variables from diagnostics

Source option:

```text
BLS -> bls
```

Newsroom fetch path:

```text
Live/services/research/newsroom_callbacks.py
_build_results(topic, sources)
```

Existing structured extension calls:

```python
results = extend_results_with_fred(topic, sources or None, results)
results = extend_results_with_sec_companyfacts(topic, sources or None, results)
```

## What this patch changes

### New / refreshed adapter

Writes:

```text
Live/services/research/bls_newsroom_adapter.py
```

The adapter creates selectable BLS Newsroom cards for:

- CPI all items
- Core CPI
- PPI final demand
- unemployment rate
- total nonfarm payrolls
- average hourly earnings

### Newsroom fetch path

Patches:

```text
Live/services/research/newsroom_callbacks.py
```

Adds:

```python
from services.research.bls_newsroom_adapter import extend_results_with_bls
```

and inserts the BLS extension inside `_build_results`, after FRED and before SEC.

### Research Analyst evidence path

Patches:

```text
Live/services/ai/research_analyst_callbacks.py
```

Adds:

```python
_bls_newsroom_evidence_markdown(...)
```

and adds BLS to the combined forced evidence context:

```text
FULL CURRENT NEWSROOM BLS EVIDENCE TABLE
```

### Patch docs folder

This patch writes its notes to:

```text
docs/patches/add_bls_newsroom_evidence_v18_2.md
```

It also removes the obsolete old path if present:

```text
docs/patch_notes/add_bls_newsroom_evidence_v18.md
```

## Safety

- No backups are created.
- No broker/order/live trading behavior is added.
- BLS rows are evidence-only and advisory/simulation-only.
- Blank or malformed BLS rows are marked explicitly.
