from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
LIVE = ROOT / "Live"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"Missing {label}: {needle}")


def main() -> int:
    app_py = read(LIVE / "app.py")
    newsroom_ui = read(LIVE / "ui" / "newsroom_ui.py")
    callbacks = read(LIVE / "services" / "ai" / "research_analyst_callbacks.py")
    css = read(LIVE / "assets" / "zz_research_analyst.css")

    require(app_py, "register_research_analyst_callbacks(app)", "Research Analyst callback registration")
    require(newsroom_ui, "research-analyst-question", "Research Analyst question box")
    require(newsroom_ui, "research-analyst-ask", "Research Analyst ask button")
    require(callbacks, "newsroom-brief-store", "brief store state")
    require(callbacks, "newsroom-results-store", "results store fallback")
    require(callbacks, "build_newsroom_evidence_packet", "Newsroom evidence packet builder")
    require(callbacks, "ResearchAnalystService", "Research Analyst prompt service")
    require(css, ".research-analyst-panel", "Research Analyst CSS")

    if str(LIVE) not in sys.path:
        sys.path.insert(0, str(LIVE))

    from services.ai.research_analyst_callbacks import register_research_analyst_callbacks  # noqa: E402

    assert callable(register_research_analyst_callbacks)
    print("OK: Newsroom Research Analyst UI and callbacks are wired.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
