from __future__ import annotations

import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from services.research.evidence_coverage import build_recommended_evidence_sources

    signature = inspect.signature(build_recommended_evidence_sources)
    assert "include_present" not in signature.parameters, signature

    callbacks_path = ROOT / "services" / "research" / "newsroom_callbacks.py"
    callbacks = callbacks_path.read_text(encoding="utf-8")
    assert "include_present=False" not in callbacks, "newsroom callback still passes include_present=False"

    result = build_recommended_evidence_sources([
        {
            "source": "BLS",
            "kind": "official-source",
            "title": "Consumer Price Index",
            "summary": "Official CPI inflation source.",
            "url": "https://www.bls.gov/cpi/",
        }
    ])
    assert isinstance(result, tuple), type(result)
    assert len(result) == 2, result
    coverage, recommendations = result
    assert isinstance(coverage, dict), type(coverage)
    assert isinstance(recommendations, list), type(recommendations)

    print("OK: Recommendation queue callback matches evidence_coverage builder signature.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
