from __future__ import annotations

from pathlib import Path


LIVE = Path(__file__).resolve().parents[1]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"Missing {label}: {needle}")


def main() -> int:
    callbacks = read(LIVE / "services" / "ai" / "research_analyst_callbacks.py")
    ui = read(LIVE / "ui" / "newsroom_ui.py")
    advisor_path = LIVE / "services" / "ai" / "advisor.py"
    advisor = read(advisor_path) if advisor_path.exists() else ""

    require(callbacks, "max_output_tokens", "correct advisor max output keyword")
    require(callbacks, "max_context_chars", "Research Analyst context budget override")
    require(callbacks, "max(800, min(8000", "Research Analyst server-side output clamp")
    require(callbacks, "Do not assign a number, level, or month-over-month change to a series", "series/value accuracy guard")
    require(callbacks, "Always end with a final read", "non-truncated final read instruction")
    require(callbacks, "separator = chr(10) + chr(10)", "safe prompt separator without malformed newline literal")

    require(ui, "Max output tokens", "clear output-token label")
    require(ui, "max=8000", "UI maximum output tokens")
    require(ui, "value=3000", "UI default output tokens")
    require(ui, "not a credit estimate", "UI token-vs-credit help text")

    if advisor and "max_context_chars: int | None = None" in advisor:
        require(advisor, "effective_max_context_chars", "advisor per-call context budget")

    print("OK: Research Analyst output budget hotfix, context budget, and anti-truncation instructions are wired.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
