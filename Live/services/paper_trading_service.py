from __future__ import annotations

from datetime import datetime
from typing import Optional

from core.PaperBroker import PaperBroker, PaperOrder
from core.RiskGuard import RiskGuard, TradeIntent, RiskDecision


class PaperTradingService:
    """
    Service layer between UI/LLM/strategies and the local PaperBroker.

    Later, this same shape can be used for IBKR paper trading through a BrokerAdapter.
    """

    def __init__(
        self,
        broker: Optional[PaperBroker] = None,
        risk_guard: Optional[RiskGuard] = None,
    ):
        self.broker = broker or PaperBroker()
        self.risk_guard = risk_guard or RiskGuard()

    def reset(self) -> None:
        self.broker.reset()

    def submit_intent(
        self,
        intent: TradeIntent,
        last_price: float,
        timestamp: Optional[datetime] = None,
        mode: str = "simulated",
    ) -> tuple[RiskDecision, Optional[PaperOrder]]:
        decision = self.risk_guard.validate(
            intent=intent,
            last_price=last_price,
            mode=mode,
        )

        if not decision.approved:
            return decision, None

        order = self.broker.submit_order(
            intent=decision.intent,
            last_price=last_price,
            timestamp=timestamp,
        )

        return decision, order

    def market_buy(
        self,
        symbol: str,
        quantity: float,
        last_price: float,
        reason: str = "",
        source: str = "manual",
    ):
        intent = TradeIntent(
            symbol=symbol,
            side="BUY",
            quantity=quantity,
            order_type="MARKET",
            reason=reason,
            source=source,
        )

        return self.submit_intent(intent, last_price=last_price)

    def market_sell(
        self,
        symbol: str,
        quantity: float,
        last_price: float,
        reason: str = "",
        source: str = "manual",
    ):
        intent = TradeIntent(
            symbol=symbol,
            side="SELL",
            quantity=quantity,
            order_type="MARKET",
            reason=reason,
            source=source,
        )

        return self.submit_intent(intent, last_price=last_price)

    def summary(self, prices: Optional[dict[str, float]] = None) -> dict:
        return self.broker.summary(prices)

    def positions_df(self):
        return self.broker.positions_df()

    def orders_df(self):
        return self.broker.orders_df()

    def fills_df(self):
        return self.broker.fills_df()