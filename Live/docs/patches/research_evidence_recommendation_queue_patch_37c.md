# Patch 37c — Research Evidence Recommendation Queue

Adds a user-reviewed missing-evidence workflow to Newsroom.

Recommendations are not silently trusted. They are pending until the user approves them.

Files:
- Live/services/research/evidence_coverage.py
- Live/scripts/check_research_evidence_recommendation_queue.py
- Live/ui/newsroom_ui.py
- Live/services/research/newsroom_callbacks.py
