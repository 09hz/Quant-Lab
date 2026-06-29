from __future__ import annotations

from pathlib import Path


LIVE = Path(__file__).resolve().parents[1]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"Missing {label}: {needle}")


def require_any(text: str, needles: tuple[str, ...], label: str) -> None:
    if not any(needle in text for needle in needles):
        raise AssertionError(f"Missing {label}: one of {needles}")


def main() -> int:
    callbacks = read(LIVE / "services" / "ai" / "research_analyst_callbacks.py")
    newsroom_callbacks = read(LIVE / "services" / "research" / "newsroom_callbacks.py")
    ui = read(LIVE / "ui" / "newsroom_ui.py")

    require(callbacks, "_build_supplemental_research_sources", "supplemental source builder")
    require(callbacks, "_enhance_research_analyst_user_prompt", "market-impact prompt enhancer")
    require(callbacks, 'State("newsroom-source-filter", "value")', "source filter state")
    require(callbacks, "Sector impact", "sector-impact answer requirement")
    require(callbacks, "Bullish or bearish current-quarter read", "bullish/bearish answer requirement")
    require(callbacks, "supplemental_research", "packet supplemental metadata")
    require(callbacks, "max(800, min(6000", "server-side output token clamp/default")

    require_any(
        newsroom_callbacks,
        ("_is_brief_addable_result", "selection_candidates"),
        "expanded lower-confidence/context source selection",
    )
    require_any(
        newsroom_callbacks,
        ("_brief_option_label", "_selection_option_label"),
        "caution source option labels",
    )

    require(ui, "min=800", "Research Analyst minimum output")
    require(ui, "max=6000", "Research Analyst maximum output")
    require(ui, "value=2000", "Research Analyst default output")
    require(ui, "2,000-3,000", "Research Analyst token recommendation help")

    print("OK: Research Analyst gap-fill sources, market-impact prompt, and better output defaults are wired.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
