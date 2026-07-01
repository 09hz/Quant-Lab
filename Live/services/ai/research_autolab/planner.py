from __future__ import annotations

from typing import Any

from .models import BacktestRequest, ResearchHypothesis


DEFAULT_SYMBOLS = ["SPY", "QQQ", "XLK", "SMH", "XLI", "IWM"]


def build_hypotheses_from_fred_manifest(
    *,
    question: str,
    series_ids: list[str],
    evidence_items: list[dict[str, Any]],
    symbols: list[str] | None = None,
) -> list[ResearchHypothesis]:
    symbols = symbols or DEFAULT_SYMBOLS
    s = set(series_ids)
    hypotheses: list[ResearchHypothesis] = []

    if {"DGS2", "DGS10", "VIXCLS", "NASDAQCOM", "SP500"}.intersection(s):
        hypotheses.append(
            ResearchHypothesis(
                id="rate_relief_tech",
                label="Rate-relief tech confirmation",
                rationale="Test whether easing yields with stable/falling volatility improves forward tech/equity returns.",
                symbols=[sym for sym in symbols if sym in {"QQQ", "XLK", "SMH", "SPY"}],
                strategy_family="macro_filter_overlay",
                filters=[
                    "DGS10 3-period change <= 0",
                    "VIXCLS 3-period change <= 0",
                    "NASDAQCOM or SP500 trend confirms",
                ],
                invalidation_rules=[
                    "DGS10 rises while VIXCLS rises",
                    "NASDAQCOM and SP500 both fail trend confirmation",
                ],
                evidence_series=["DGS2", "DGS10", "VIXCLS", "NASDAQCOM", "SP500"],
            )
        )

    if {"AMTMNO", "IPMAN", "INDPRO", "DGORDER", "DCOILWTICO"}.intersection(s):
        hypotheses.append(
            ResearchHypothesis(
                id="manufacturing_oil_relief",
                label="Manufacturing momentum plus oil relief",
                rationale="Test whether improving manufacturing indicators plus falling oil supports cyclicals and industrial-linked technology.",
                symbols=[sym for sym in symbols if sym in {"XLI", "SMH", "SPY", "QQQ"}],
                strategy_family="macro_filter_overlay",
                filters=[
                    "AMTMNO 3-period change > 0",
                    "DCOILWTICO 3-period change < 0",
                    "IPMAN or INDPRO trend confirms when available",
                ],
                invalidation_rules=[
                    "IPMAN and INDPRO decline",
                    "DCOILWTICO reverses sharply higher",
                ],
                evidence_series=["AMTMNO", "IPMAN", "INDPRO", "DGORDER", "DCOILWTICO"],
            )
        )

    if {"PAYEMS", "UNRATE", "UMCSENT", "VIXCLS"}.intersection(s):
        hypotheses.append(
            ResearchHypothesis(
                id="labor_sentiment_risk_filter",
                label="Labor-sentiment risk filter",
                rationale="Test whether healthy labor with stable volatility supports risk assets despite weak sentiment.",
                symbols=[sym for sym in symbols if sym in {"SPY", "QQQ", "IWM"}],
                strategy_family="volatility_filter_overlay",
                filters=[
                    "PAYEMS trend >= 0",
                    "UNRATE trend <= 0",
                    "VIXCLS trend <= 0",
                    "UMCSENT not deteriorating sharply",
                ],
                invalidation_rules=[
                    "UNRATE rises and VIXCLS rises",
                    "PAYEMS weakens materially",
                ],
                evidence_series=["PAYEMS", "UNRATE", "UMCSENT", "VIXCLS"],
            )
        )

    return hypotheses


def build_backtest_requests(
    hypotheses: list[ResearchHypothesis],
    *,
    timeframe: str = "1 day",
    start: str | None = None,
    end: str | None = None,
) -> list[BacktestRequest]:
    requests: list[BacktestRequest] = []
    base_parameter_grid = [
        {"lookback": 20, "holding_days": 5},
        {"lookback": 50, "holding_days": 10},
        {"lookback": 100, "holding_days": 20},
    ]

    for hypothesis in hypotheses:
        for symbol in hypothesis.symbols:
            for params in base_parameter_grid:
                requests.append(
                    BacktestRequest(
                        hypothesis_id=hypothesis.id,
                        symbol=symbol,
                        strategy_family=hypothesis.strategy_family,
                        timeframe=timeframe,
                        start=start,
                        end=end,
                        parameters=params,
                        macro_filters=hypothesis.filters,
                    )
                )

    return requests
