from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LIVE = ROOT / "Live"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"Missing {label}: {needle}")


def main() -> int:
    newsroom_ui = read(LIVE / "ui" / "newsroom_ui.py")
    analyst_callbacks = read(LIVE / "services" / "ai" / "research_analyst_callbacks.py")
    newsroom_callbacks = read(LIVE / "services" / "research" / "newsroom_callbacks.py")
    css = read(LIVE / "assets" / "zz_research_analyst.css")

    require(newsroom_ui, "research-analyst-control-max-output", "left-side max-output control class")
    require(newsroom_ui, "Max output / credits", "max output credits label")
    require(css, "research-analyst-control-max-output", "max-output layout CSS")

    require(analyst_callbacks, "_enhance_research_analyst_question", "market-impact prompt helper")
    require(analyst_callbacks, "Market impact", "market impact answer requirement")
    require(analyst_callbacks, "What to watch next", "what-to-watch answer requirement")
    require(analyst_callbacks, "analysis_question", "enhanced prompt variable")

    require(newsroom_callbacks, "_is_brief_addable_result", "brief addable helper")
    require(newsroom_callbacks, "_brief_option_label", "brief option label helper")
    require(newsroom_callbacks, "context/lower-confidence", "lower-confidence source option label")
    require(newsroom_callbacks, "_is_brief_addable_result(item)", "add selected uses addable helper")
    require(newsroom_callbacks, "Brief caution", "brief caution markdown")

    print("OK: Research Analyst UX, market-impact prompt, and lower-confidence source selection are wired.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
