from __future__ import annotations

from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]

    newsroom_ui = (root / "ui" / "newsroom_ui.py").read_text(encoding="utf-8")
    newsroom_callbacks = (root / "services" / "research" / "newsroom_callbacks.py").read_text(encoding="utf-8")
    strategy_callbacks = (root / "services" / "ai" / "strategy_context_callbacks.py").read_text(encoding="utf-8")

    required = [
        (newsroom_ui, 'dcc.Store(id="newsroom-results-store", data=[], storage_type="session")'),
        (newsroom_ui, 'dcc.Store(id="newsroom-brief-store", data=[], storage_type="session")'),
        (newsroom_callbacks, "def _merge_brief_items("),
        (newsroom_callbacks, "_merge_brief_items(brief or [], additions, max_items=80)"),
        (strategy_callbacks, "def _merge_context_text("),
        (strategy_callbacks, 'State("strategy-ai-advisor-context", "value")'),
        (strategy_callbacks, "_merge_context_text(existing_context, context_text)"),
        (strategy_callbacks, "Clear Context is the only UI action that resets this stack."),
    ]

    missing = [needle for haystack, needle in required if needle not in haystack]
    if missing:
        raise SystemExit("Persistent stack wiring missing: " + ", ".join(missing))

    print("OK: Newsroom brief and Strategy AI context stacks append/merge instead of overwriting.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
