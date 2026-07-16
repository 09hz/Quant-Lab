# v24.9.4 — Research Loop Evaluation Mode UI + Real Adapter Visibility

## Purpose

Make the Research Loop browser panel show and control whether the loop is using:

```text
proxy
hybrid_safe
real_required
```

This patch also makes browser results show the `evaluation_source`, so it is obvious whether a result came from the proxy scorer, real BackTestEngine adapter, or proxy fallback.

## Evaluation modes

```text
proxy
  Always use deterministic proxy scoring.

hybrid_safe
  Try real BackTestEngine first.
  If not safely callable/parseable, fall back to proxy and label the fallback.

real_required
  Try real BackTestEngine.
  If unavailable/incompatible, reject the candidate instead of using proxy.
```

## Safety

- Research/simulation only
- No broker calls
- No live trading
- No order placement
- Sets process-level broker disable flags during adapter probing
- Skips callable names containing live/order/broker/execute/trade/place/submit/send
- Does not touch Data Library files
