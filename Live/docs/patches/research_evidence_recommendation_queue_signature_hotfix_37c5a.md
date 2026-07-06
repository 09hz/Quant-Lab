# Research Evidence Recommendation Queue Signature Hotfix 37c5a

## Problem

The Dash callback called:

```python
build_recommended_evidence_sources(current_brief, include_present=False)
```

but the installed `services.research.evidence_coverage.build_recommended_evidence_sources`
function in this branch does not accept the `include_present` keyword. Dash raised:

```text
TypeError: build_recommended_evidence_sources() got an unexpected keyword argument 'include_present'
```

## Fix

The callback now calls the currently installed builder signature:

```python
build_recommended_evidence_sources(current_brief)
```

This keeps Generate Missing Evidence Recommendations from failing before the UI can show
recommendations or a visible status message.

## Check

```powershell
python -m py_compile .\Live\services\research\newsroom_callbacks.py
python .\Live\scripts\check_research_evidence_recommendation_queue_signature.py
```
