from __future__ import annotations

from datetime import datetime
from typing import Optional

from core.PaperBroker import PaperBroker, PaperOrder
from core.RiskGuard import RiskGuard, TradeIntent, RiskDecision


class PaperTradingService:
    """
    Service layer between UI/LLM/strategies and the local PaperBroker.

    This layer blocks invalid position actions before an order reaches
    PaperBroker.

    Rules:
    - Normal SELL can only reduce an existing long.
    - Normal SELL cannot accidentally open a short.
    - SHORT SELL can open/add short only when allow_short=True.
    - SHORT BUY can only cover an existing short.
    - SHORT BUY cannot cover more than the current short size.
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

    def _current_position_qty(self, symbol: str) -> float:
        symbol = str(symbol or "").upper().strip()

        try:
            position = self.broker.positions.get(symbol)
            if position is None:
                return 0.0

            return float(getattr(position, "quantity", 0.0) or 0.0)
        except Exception:
            return 0.0

    def _reject(self, intent: TradeIntent, message: str) -> RiskDecision:
        """
        Build a RiskDecision rejection while staying compatible with slightly
        different RiskDecision dataclass constructor styles.
        """
        try:
            return RiskDecision(
                approved=False,
                message=message,
                intent=intent,
            )
        except TypeError:
            try:
                return RiskDecision(False, message, intent)
            except TypeError:
                return RiskDecision(
                    approved=False,
                    message=message,
                )

    def _is_short_sell_intent(self, intent: TradeIntent) -> bool:
        source = str(getattr(intent, "source", "") or "").lower()
        reason = str(getattr(intent, "reason", "") or "").lower()

        return (
            source.startswith("manual_short")
            or "short sell" in reason
        )

    def _is_short_cover_intent(self, intent: TradeIntent) -> bool:
        source = str(getattr(intent, "source", "") or "").lower()
        reason = str(getattr(intent, "reason", "") or "").lower()

        return (
            source.startswith("manual_short_cover")
            or "short cover" in reason
        )

    def _validate_position_action(
        self,
        intent: TradeIntent,
        current_position: float,
        allow_short: bool,
    ) -> Optional[RiskDecision]:
        symbol = str(intent.symbol or "").upper().strip()
        side = str(intent.side or "").upper().strip()
        quantity = float(intent.quantity or 0)

        if quantity <= 0:
            return self._reject(intent, "Quantity must be greater than zero.")

        is_short_sell = self._is_short_sell_intent(intent)
        is_short_cover = self._is_short_cover_intent(intent)

        # ------------------------------------------------------------
        # Normal SELL: close/reduce long only.
        # It should never open a short by accident.
        # ------------------------------------------------------------
        if side == "SELL" and not is_short_sell:
            if current_position <= 0:
                return self._reject(
                    intent,
                    f"Invalid sell: no long position is open for {symbol}. "
                    f"Use Short Sell if you want to open a short.",
                )

            if quantity > current_position:
                return self._reject(
                    intent,
                    f"Invalid sell: quantity {quantity:g} is greater than "
                    f"your long position of {current_position:g} shares in {symbol}.",
                )

            return None

        # ------------------------------------------------------------
        # Short SELL: open/add short only when enabled.
        # ------------------------------------------------------------
        if side == "SELL" and is_short_sell:
            if not allow_short:
                return self._reject(
                    intent,
                    "Short selling is disabled. Select Allow Shorts first.",
                )

            # Do not allow short-selling while already long.
            # The user should use normal SELL to reduce/close the long first.
            if current_position > 0:
                return self._reject(
                    intent,
                    f"Invalid short sell: you currently have a long position "
                    f"of {current_position:g} shares in {symbol}. "
                    f"Close the long position before opening a short.",
                )

            return None

        # ------------------------------------------------------------
        # Short BUY: cover an existing short only.
        # ------------------------------------------------------------
        if side == "BUY" and is_short_cover:
            if current_position >= 0:
                return self._reject(
                    intent,
                    f"Invalid short buy: no short position is open for {symbol}.",
                )

            short_qty = abs(current_position)

            if quantity > short_qty:
                return self._reject(
                    intent,
                    f"Invalid short buy: quantity {quantity:g} is greater than "
                    f"your short position of {short_qty:g} shares in {symbol}.",
                )

            return None

        # Normal BUY is always allowed. It can open long or, depending on your
        # broker model, cover short. The explicit SHORT BUY button gives you
        # cleaner control, but this keeps BUY flexible.
        return None

    def submit_intent(
        self,
        intent: TradeIntent,
        last_price: float,
        timestamp: Optional[datetime] = None,
        mode: str = "simulated",
        allow_short: bool = False,
    ) -> tuple[RiskDecision, Optional[PaperOrder]]:
        current_position = self._current_position_qty(intent.symbol)

        position_rejection = self._validate_position_action(
            intent=intent,
            current_position=current_position,
            allow_short=allow_short,
        )

        if position_rejection is not None:
            return position_rejection, None

        try:
            decision = self.risk_guard.validate(
                intent=intent,
                last_price=last_price,
                mode=mode,
                current_position=current_position,
                allow_short_override=allow_short,
            )
        except TypeError:
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
        allow_short: bool = False,
    ):
        intent = TradeIntent(
            symbol=symbol,
            side="BUY",
            quantity=quantity,
            order_type="MARKET",
            reason=reason,
            source=source,
        )

        return self.submit_intent(
            intent,
            last_price=last_price,
            allow_short=allow_short,
        )

    def market_sell(
        self,
        symbol: str,
        quantity: float,
        last_price: float,
        reason: str = "",
        source: str = "manual",
        allow_short: bool = False,
    ):
        intent = TradeIntent(
            symbol=symbol,
            side="SELL",
            quantity=quantity,
            order_type="MARKET",
            reason=reason,
            source=source,
        )

        return self.submit_intent(
            intent,
            last_price=last_price,
            allow_short=allow_short,
        )

    def summary(self, prices: Optional[dict[str, float]] = None) -> dict:
        return self.broker.summary(prices)

    def positions_df(self):
        return self.broker.positions_df()

    def orders_df(self):
        return self.broker.orders_df()

    def fills_df(self):
        return self.broker.fills_df()