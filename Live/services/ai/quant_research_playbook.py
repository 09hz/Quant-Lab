from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class QuantHypothesis:
    name: str
    thesis: str
    symbols_to_test: list[str]
    strategy_family: str
    timeframe_candidates: list[str]
    filters: list[str]
    required_evidence: list[str]
    invalidation_rules: list[str]
    metrics: list[str]
    confidence: str


def _clean(value: Any, *, max_len: int = 900) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) > max_len:
        return text[: max_len - 1].rstrip() + "..."
    return text


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        text = str(value).strip()
        if not text or text == ".":
            return None
        return float(text)
    except Exception:
        return None


def _series_id_from_item(item: dict[str, Any]) -> str:
    metadata = item.get("metadata") or {}
    for key in ("series_id", "fred_series_id", "id"):
        value = metadata.get(key)
        if value:
            return str(value).strip().upper()

    title = str(item.get("title") or "")
    summary = str(item.get("summary") or "")
    haystack = f"{title} {summary}".upper()
    known = (
        "CPIAUCSL", "CPILFESL", "PCEPI", "PCEPILFE", "FEDFUNDS", "DGS2", "DGS10",
        "T10Y2Y", "SP500", "NASDAQCOM", "VIXCLS", "NFCI", "BAA10Y", "IPMAN",
        "INDPRO", "AMTMNO", "DGORDER", "MANEMP", "ICSA", "RSAFS", "PCE",
        "PAYEMS", "UNRATE", "UMCSENT",
    )
    for series_id in known:
        if series_id in haystack:
            return series_id
    return ""


def _extract_observation_value(row: Any) -> float | None:
    if isinstance(row, dict):
        return _to_float(row.get("value"))
    return _to_float(row)


def _extract_observation_date(row: Any) -> str:
    if isinstance(row, dict):
        return str(row.get("date") or "")
    return ""


def _series_state_from_item(item: dict[str, Any]) -> dict[str, Any] | None:
    series_id = _series_id_from_item(item)
    if not series_id:
        return None

    metadata = item.get("metadata") or {}
    latest = metadata.get("latest_observation") or metadata.get("latest") or {}
    previous = metadata.get("previous_observation") or metadata.get("previous") or {}

    latest_value = _extract_observation_value(latest)
    previous_value = _extract_observation_value(previous)

    deltas = metadata.get("trend_deltas") or metadata.get("deltas") or {}
    one_period = _to_float(deltas.get("1_period") if isinstance(deltas, dict) else None)
    three_period = _to_float(deltas.get("3_period") if isinstance(deltas, dict) else None)
    six_period = _to_float(deltas.get("6_period") if isinstance(deltas, dict) else None)

    if one_period is None and latest_value is not None and previous_value is not None:
        one_period = latest_value - previous_value

    return {
        "series_id": series_id,
        "title": _clean(item.get("title"), max_len=160),
        "source": _clean(item.get("source"), max_len=80),
        "category": _clean(metadata.get("category") or item.get("topic"), max_len=80),
        "latest_date": _extract_observation_date(latest) or str(item.get("published_at") or ""),
        "latest_value": latest_value,
        "previous_value": previous_value,
        "change_1_period": one_period,
        "change_3_period": three_period,
        "change_6_period": six_period,
        "confidence": _clean(item.get("confidence") or item.get("validity"), max_len=80),
    }


def extract_series_state(evidence_items: list[dict[str, Any]] | tuple[dict[str, Any], ...]) -> dict[str, dict[str, Any]]:
    """Extract lightweight macro/market state from Research Analyst evidence items."""
    state: dict[str, dict[str, Any]] = {}
    for item in evidence_items or []:
        if not isinstance(item, dict):
            continue
        row = _series_state_from_item(item)
        if not row:
            continue
        state.setdefault(row["series_id"], row)
    return state


def _change(state: dict[str, dict[str, Any]], series_id: str, key: str = "change_1_period") -> float | None:
    row = state.get(series_id.upper()) or {}
    return _to_float(row.get(key))


def _has_value(state: dict[str, dict[str, Any]], series_id: str) -> bool:
    row = state.get(series_id.upper()) or {}
    return _to_float(row.get("latest_value")) is not None


def infer_quant_regime(
    *,
    question: str = "",
    evidence_items: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
) -> dict[str, Any]:
    """Infer a research-only market regime from confirmed/proxy evidence."""
    state = extract_series_state(list(evidence_items or []))
    labels: list[str] = []
    positives: list[str] = []
    negatives: list[str] = []
    missing: list[str] = []

    payems_3 = _change(state, "PAYEMS", "change_3_period")
    unrate_3 = _change(state, "UNRATE", "change_3_period")
    sentiment_3 = _change(state, "UMCSENT", "change_3_period")
    dgs2_1 = _change(state, "DGS2")
    dgs10_1 = _change(state, "DGS10")
    vix_1 = _change(state, "VIXCLS")
    nasdaq_1 = _change(state, "NASDAQCOM")
    sp500_1 = _change(state, "SP500")

    if payems_3 is not None and payems_3 > 0:
        labels.append("labor_supportive")
        positives.append("PAYEMS is improving over the available multi-period window.")
    elif not _has_value(state, "PAYEMS"):
        missing.append("PAYEMS labor breadth")

    if unrate_3 is not None and unrate_3 <= 0:
        labels.append("labor_slack_stable_or_improving")
        positives.append("UNRATE is flat/down over the available multi-period window.")
    elif not _has_value(state, "UNRATE"):
        missing.append("UNRATE labor slack")

    if sentiment_3 is not None and sentiment_3 < 0:
        labels.append("consumer_sentiment_weakening")
        negatives.append("UMCSENT is weakening over the available multi-period window.")
    elif not _has_value(state, "UMCSENT"):
        missing.append("UMCSENT consumer sentiment")

    if dgs2_1 is not None and dgs2_1 < 0 and dgs10_1 is not None and dgs10_1 < 0:
        labels.append("rates_easing_short_term")
        positives.append("2Y and 10Y yields are easing over the latest available observation.")
    elif not (_has_value(state, "DGS2") and _has_value(state, "DGS10")):
        missing.append("DGS2/DGS10 rate pressure")

    if vix_1 is not None and vix_1 < 0:
        labels.append("volatility_easing")
        positives.append("VIX is easing over the latest available observation.")
    elif not _has_value(state, "VIXCLS"):
        missing.append("VIX risk sentiment")

    if (nasdaq_1 is not None and nasdaq_1 < 0) or (sp500_1 is not None and sp500_1 < 0):
        labels.append("equity_confirmation_soft")
        negatives.append("Broad equity proxies are not confirming a clean risk-on move.")
    elif not (_has_value(state, "NASDAQCOM") or _has_value(state, "SP500")):
        missing.append("NASDAQ/SP500 equity confirmation")

    for series_id, label in (
        ("CPIAUCSL", "headline CPI"),
        ("CPILFESL", "core CPI"),
        ("PCEPI", "PCE inflation"),
        ("PCEPILFE", "core PCE inflation"),
        ("FEDFUNDS", "Fed funds/policy rate"),
        ("IPMAN", "manufacturing production"),
        ("AMTMNO", "manufacturing new orders"),
        ("DGORDER", "durable goods orders"),
    ):
        if not _has_value(state, series_id):
            missing.append(label)

    if positives and negatives:
        regime_label = "mixed_macro"
    elif positives and not negatives:
        regime_label = "constructive_but_unconfirmed"
    elif negatives and not positives:
        regime_label = "defensive_or_risk_off"
    else:
        regime_label = "insufficient_evidence"

    return {
        "schema_version": "1.0",
        "regime_label": regime_label,
        "labels": labels,
        "supportive_evidence": positives,
        "risk_evidence": negatives,
        "missing_evidence": sorted(set(missing)),
        "series_state": state,
        "research_only": True,
    }


def _default_symbols(symbol: str = "") -> list[str]:
    base = ["SPY", "QQQ", "SMH", "XLK", "XLI", "XLY", "DIA"]
    clean_symbol = _clean(symbol, max_len=16).upper()
    if clean_symbol and clean_symbol not in base:
        return [clean_symbol] + base
    return base


def build_quant_research_playbook(
    *,
    question: str = "",
    evidence_items: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
    symbol: str = "",
    topic: str = "",
    max_hypotheses: int = 5,
) -> dict[str, Any]:
    """
    Convert Research Analyst evidence into research-only quant hypotheses.

    This module never places trades, never calls broker APIs, and never treats an
    AI summary as validated alpha. It produces test plans that require backtests.
    """
    regime = infer_quant_regime(question=question, evidence_items=list(evidence_items or []))
    symbols = _default_symbols(symbol)
    hypotheses: list[QuantHypothesis] = []

    hypotheses.append(
        QuantHypothesis(
            name="Mixed labor-support / weak-sentiment regime",
            thesis=(
                "When labor breadth is firm but consumer sentiment is falling, equity markets may become choppier: "
                "macro activity is supported, but forward demand confidence is deteriorating."
            ),
            symbols_to_test=symbols,
            strategy_family="trend-following versus mean-reversion comparison",
            timeframe_candidates=["1 day", "1 hour", "15 min"],
            filters=[
                "PAYEMS 3-period change > 0",
                "UNRATE 3-period change <= 0",
                "UMCSENT 3-period change < 0",
                "Compare results with and without VIX filter",
            ],
            required_evidence=["PAYEMS", "UNRATE", "UMCSENT", "VIXCLS", "SP500", "NASDAQCOM"],
            invalidation_rules=[
                "UMCSENT stabilizes or turns positive over the 3-period window.",
                "UNRATE rises materially over the 3-period window.",
                "SPY/QQQ price trend confirms a strong directional breakout with expanding breadth.",
            ],
            metrics=["CAGR", "max drawdown", "Sharpe", "profit factor", "win rate", "trade count", "exposure"],
            confidence="medium" if regime["regime_label"] == "mixed_macro" else "low",
        )
    )

    hypotheses.append(
        QuantHypothesis(
            name="Rate-relief tech confirmation test",
            thesis=(
                "Tech/growth may benefit when yields ease, but the setup should require price and volatility confirmation "
                "because lower yields alone do not guarantee risk-on behavior."
            ),
            symbols_to_test=["QQQ", "SMH", "XLK", "SPY"],
            strategy_family="breakout/trend filter with macro confirmation",
            timeframe_candidates=["1 day", "1 hour"],
            filters=[
                "DGS2 and DGS10 latest change < 0",
                "VIXCLS latest change <= 0",
                "QQQ above medium moving average or recent breakout level",
                "Reject signal if NASDAQ/SP500 are falling with rising VIX",
            ],
            required_evidence=["DGS2", "DGS10", "VIXCLS", "NASDAQCOM", "SP500"],
            invalidation_rules=[
                "2Y/10Y yields reverse higher.",
                "VIX rises while QQQ breaks below trend support.",
                "Inflation data re-accelerates after confirmation is added.",
            ],
            metrics=["excess return versus SPY", "max drawdown", "hit rate after yield-easing days", "average trade duration"],
            confidence="low-to-medium",
        )
    )

    hypotheses.append(
        QuantHypothesis(
            name="Manufacturing confirmation filter",
            thesis=(
                "Manufacturing exposure should not be treated as bullish from labor data alone; it needs confirmation from "
                "production, new orders, durable goods, or PMI-like evidence."
            ),
            symbols_to_test=["XLI", "DIA", "SPY", "CAT", "DE", "HON"],
            strategy_family="sector rotation / confirmation filter",
            timeframe_candidates=["1 day"],
            filters=[
                "Require IPMAN or INDPRO trend > 0",
                "Require AMTMNO or DGORDER trend > 0 when available",
                "Avoid bullish manufacturing read if UMCSENT and orders both deteriorate",
            ],
            required_evidence=["IPMAN", "INDPRO", "AMTMNO", "DGORDER", "UMCSENT"],
            invalidation_rules=[
                "IPMAN/INDPRO roll over.",
                "New orders deteriorate across 3-period and 6-period windows.",
                "Credit spreads or financial conditions tighten materially.",
            ],
            metrics=["sector relative strength versus SPY", "drawdown", "return by macro regime", "turnover"],
            confidence="low" if "manufacturing production" in regime["missing_evidence"] else "medium",
        )
    )

    text = f"{question} {topic}".lower()
    if any(term in text for term in ("iran", "war", "geopolitical", "political", "oil", "sanction", "shipping", "election")):
        hypotheses.append(
            QuantHypothesis(
                name="Geopolitical risk-premium overlay",
                thesis=(
                    "Political/geopolitical shocks can keep markets mixed even when some macro data improves, because oil risk, "
                    "shipping risk, sanctions, and headline uncertainty can lift risk premia."
                ),
                symbols_to_test=["SPY", "QQQ", "SMH", "XLI", "XLE", "USO"],
                strategy_family="risk overlay / position-size filter",
                timeframe_candidates=["1 day", "1 hour"],
                filters=[
                    "Use only confirmed Newsroom geopolitical sources for current facts.",
                    "Monitor VIX, oil/energy proxy, yields, and broad index confirmation.",
                    "Reduce size or require stronger price confirmation during elevated headline risk.",
                ],
                required_evidence=["confirmed geopolitical/news source", "VIXCLS", "DGS10", "SP500", "NASDAQCOM", "oil or energy proxy"],
                invalidation_rules=[
                    "Confirmed de-escalation plus falling VIX/oil risk premium.",
                    "Market breadth and price trend confirm sustained risk-on behavior.",
                ],
                metrics=["drawdown during headline-risk windows", "gap risk", "overnight return", "volatility-adjusted return"],
                confidence="low until current-event sources are confirmed",
            )
        )

    max_count = max(1, min(8, int(max_hypotheses or 5)))
    hypothesis_dicts = [asdict(item) for item in hypotheses[:max_count]]

    return {
        "schema_version": "1.0",
        "enabled": True,
        "research_only": True,
        "regime": regime,
        "hypotheses": hypothesis_dicts,
        "backtest_plan": {
            "objective": "Convert the evidence packet into falsifiable strategy tests before making trading decisions.",
            "symbols": symbols,
            "timeframes": ["1 day", "1 hour", "15 min"],
            "date_range_guidance": "Use enough history to cover multiple macro regimes; avoid optimizing on only the current episode.",
            "comparison": [
                "trend-following baseline",
                "mean-reversion baseline",
                "same strategy with and without macro filters",
                "same strategy with and without VIX/rate/geopolitical overlays",
            ],
            "required_outputs": [
                "per-symbol metrics",
                "aggregate metrics",
                "trade ledger",
                "drawdown by regime",
                "best/worst symbols",
                "out-of-sample or walk-forward split",
            ],
        },
        "safeguards": [
            "Research-only: do not place live trades from this playbook.",
            "No broker access, no order placement, and no automated execution.",
            "Treat hypotheses as unvalidated until backtested across symbols and regimes.",
            "Require source-backed current facts; use scenario language for unconfirmed events.",
        ],
    }


def playbook_to_markdown(playbook: dict[str, Any]) -> str:
    if not playbook or not playbook.get("enabled"):
        return ""

    regime = playbook.get("regime") or {}
    lines: list[str] = [
        "## Quant research playbook",
        "",
        f"Regime label: {regime.get('regime_label', 'unknown')}",
        "",
    ]

    supportive = regime.get("supportive_evidence") or []
    risks = regime.get("risk_evidence") or []
    missing = regime.get("missing_evidence") or []

    if supportive:
        lines.append("Supportive evidence:")
        lines.extend(f"- {item}" for item in supportive[:8])
        lines.append("")
    if risks:
        lines.append("Risk evidence:")
        lines.extend(f"- {item}" for item in risks[:8])
        lines.append("")
    if missing:
        lines.append("Missing evidence to research before high-confidence conclusions:")
        lines.extend(f"- {item}" for item in missing[:12])
        lines.append("")

    lines.append("Testable hypotheses:")
    for index, hypothesis in enumerate(playbook.get("hypotheses") or [], start=1):
        lines.append(f"{index}. {hypothesis.get('name', 'Hypothesis')}")
        lines.append(f"   Thesis: {hypothesis.get('thesis', '')}")
        symbols = ", ".join(hypothesis.get("symbols_to_test") or [])
        if symbols:
            lines.append(f"   Symbols to test: {symbols}")
        filters = hypothesis.get("filters") or []
        if filters:
            lines.append("   Filters:")
            lines.extend(f"   - {item}" for item in filters[:6])
        invalidation = hypothesis.get("invalidation_rules") or []
        if invalidation:
            lines.append("   Invalidation:")
            lines.extend(f"   - {item}" for item in invalidation[:4])
        lines.append(f"   Confidence: {hypothesis.get('confidence', 'low')}")
        lines.append("")

    plan = playbook.get("backtest_plan") or {}
    lines.append("Backtest plan:")
    lines.append(f"- Objective: {plan.get('objective', '')}")
    if plan.get("comparison"):
        lines.append("- Compare:")
        lines.extend(f"  - {item}" for item in plan.get("comparison", [])[:8])
    if plan.get("required_outputs"):
        lines.append("- Required outputs:")
        lines.extend(f"  - {item}" for item in plan.get("required_outputs", [])[:10])

    lines.append("")
    lines.append("Safeguards:")
    lines.extend(f"- {item}" for item in playbook.get("safeguards", [])[:8])

    return "\n".join(lines).strip()
