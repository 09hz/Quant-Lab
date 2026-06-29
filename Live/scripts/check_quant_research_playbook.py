from __future__ import annotations

import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _live_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main() -> int:
    repo_root = _repo_root()
    live_root = _live_root()

    sys.path.insert(0, str(live_root))
    sys.path.insert(0, str(repo_root))

    service_path = live_root / "services" / "ai" / "quant_research_playbook.py"
    callback_path = live_root / "services" / "ai" / "research_analyst_callbacks.py"

    if not service_path.exists():
        raise SystemExit(f"Missing {service_path}")
    if not callback_path.exists():
        raise SystemExit(f"Missing {callback_path}")

    from services.ai.quant_research_playbook import (  # noqa: PLC0415
        build_quant_research_playbook,
        extract_series_state,
        infer_quant_regime,
        playbook_to_markdown,
    )

    sample_items = [
        {
            "title": "FRED structured data: PAYEMS",
            "source": "FRED",
            "metadata": {
                "series_id": "PAYEMS",
                "latest_observation": {"date": "2026-05-01", "value": 159001.0},
                "previous_observation": {"date": "2026-04-01", "value": 158829.0},
                "trend_deltas": {"1_period": 172.0, "3_period": 565.0, "6_period": 552.0},
            },
        },
        {
            "title": "FRED structured data: UNRATE",
            "source": "FRED",
            "metadata": {
                "series_id": "UNRATE",
                "latest_observation": {"date": "2026-05-01", "value": 4.3},
                "previous_observation": {"date": "2026-04-01", "value": 4.3},
                "trend_deltas": {"1_period": 0.0, "3_period": -0.1, "6_period": -0.2},
            },
        },
        {
            "title": "FRED structured data: UMCSENT",
            "source": "FRED",
            "metadata": {
                "series_id": "UMCSENT",
                "latest_observation": {"date": "2026-05-01", "value": 44.8},
                "previous_observation": {"date": "2026-04-01", "value": 49.8},
                "trend_deltas": {"1_period": -5.0, "3_period": -11.8, "6_period": -6.2},
            },
        },
    ]

    state = extract_series_state(sample_items)
    if not {"PAYEMS", "UNRATE", "UMCSENT"}.issubset(state):
        raise SystemExit(f"Series extraction failed: {state}")

    regime = infer_quant_regime(question="How could a trader use this?", evidence_items=sample_items)
    if regime.get("regime_label") != "mixed_macro":
        raise SystemExit(f"Expected mixed_macro regime, got: {regime}")

    playbook = build_quant_research_playbook(
        question="How could a quant trader use this for a backtest?",
        evidence_items=sample_items,
        symbol="QQQ",
        topic="tech manufacturing mixed quarter",
    )
    if not playbook.get("enabled"):
        raise SystemExit("Playbook was not enabled.")
    if len(playbook.get("hypotheses") or []) < 3:
        raise SystemExit("Expected at least 3 quant hypotheses.")
    if not any("Research-only" in item for item in playbook.get("safeguards", [])):
        raise SystemExit("Research-only safeguard missing.")

    markdown = playbook_to_markdown(playbook)
    for phrase in (
        "Quant research playbook",
        "Regime label: mixed_macro",
        "Testable hypotheses",
        "Backtest plan",
        "Safeguards",
    ):
        if phrase not in markdown:
            raise SystemExit(f"Missing phrase in playbook markdown: {phrase}")

    callback_text = callback_path.read_text(encoding="utf-8")
    required_callback_phrases = (
        "quant_research_playbook",
        "build_quant_research_playbook",
        "playbook_to_markdown",
        "Quant research playbook",
        "Never present the quant playbook as a live trade recommendation",
    )
    for phrase in required_callback_phrases:
        if phrase not in callback_text:
            raise SystemExit(f"Callback wiring missing phrase: {phrase}")

    print("OK: Quant Research Playbook backend and Research Analyst context wiring are applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
