# Patch 36f - Research Analyst output budget fix

## Problem

The Newsroom Research Analyst UI allowed a large max output value, but the callback passed `max_output=...` into the shared advisor service. The advisor service expects `max_output_tokens=...`, so the Research Analyst call could fall back to the advisor's default output size and answers could stop mid-thought.

## Changes

- Fixes the Research Analyst callback to call the advisor with `max_output_tokens`.
- Adds an optional per-call `max_context_chars` budget to `AIAdvisorService.ask`.
- Gives Research Analyst calls a larger context budget so evidence packets are less likely to lose source/value labels.
- Raises the Research Analyst UI default to 3,000 output tokens and max to 8,000.
- Renames the UI control to "Max output tokens" and explains that it is not a credit estimate.
- Adds stricter prompt rules:
  - do not attach a value/change to a series unless the same evidence item contains both,
  - label search/landing pages as discovery sources,
  - keep the answer compact enough to finish,
  - always end with a final read.

## Safety

The patch does not enable unrestricted browsing or broker access. It only fixes the output/context budget path for user-selected Newsroom evidence and approved supplemental source candidates.
