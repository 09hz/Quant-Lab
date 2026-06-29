# Patch 36f2 - Research Analyst output budget hotfix

## Problem

Patch 36f could leave `research_analyst_callbacks.py` with a malformed string literal in the advisor call path. The UI label also did not reliably update to `Max output tokens`.

## Fix

- Rewrites `_call_ai_research_advisor` with a safe prompt-combine path that uses `chr(10)` instead of embedded newline literals.
- Passes `max_output_tokens` into the shared advisor service.
- Keeps the Research Analyst context budget larger when the advisor supports `max_context_chars`.
- Rewrites the Research Analyst prompt enhancer so answers must include sector impact, market impact, correlation path, and a final bullish/bearish/mixed read.
- Repairs the Newsroom UI label and sets default/max output tokens to 3000/8000.
- Updates the checker.

## Safety

This does not enable unrestricted AI browsing. It only fixes output budget handling for the controlled Newsroom evidence-packet flow.
