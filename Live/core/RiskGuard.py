from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class TradeIntent:
    symbol: str
    side: str
    quantity: float
    order_type: str = "MARKET"
    limit_price: Optional[float] = None
    reason: str = ""
    source: str = "manual"


@dataclass
class RiskDecision:
    approved: bool
    message: str
    intent: Optional[TradeIntent] = None


class RiskGuard:
    def __init__(
        self,
        allowed_symbols: Optional[set[str]] = None,
        max_quantity: float = 1_000,
        max_notional: float = 25_000,
        allow_short: bool = False,
        live_trading_enabled: bool = False,
    ):
        self.allowed_symbols = allowed_symbols
        self.max_quantity = float(max_quantity)
        self.max_notional = float(max_notional)
        self.allow_short = bool(allow_short)
        self.live_trading_enabled = bool(live_trading_enabled)

    def validate(
        self,
        intent: TradeIntent,
        last_price: Optional[float],
        mode: str = "simulated",
    ) -> RiskDecision:
        if intent is None:
            return RiskDecision(False, "No trade intent supplied.")

        symbol = str(intent.symbol or "").upper().strip()
        side = str(intent.side or "").upper().strip()
        order_type = str(intent.order_type or "MARKET").upper().strip()

        if not symbol:
            return RiskDecision(False, "Missing symbol.")

        if self.allowed_symbols is not None and symbol not in self.allowed_symbols:
            return RiskDecision(False, f"{symbol} is not in the allowed symbol list.")

        if side not in {"BUY", "SELL"}:
            return RiskDecision(False, f"Unsupported side: {side}")

        if side == "SELL" and not self.allow_short:
            # Selling is still allowed later if it closes an existing long position.
            # The PaperBroker will decide if there is position available.
            pass

        try:
            quantity = float(intent.quantity)
        except Exception:
            return RiskDecision(False, "Quantity must be numeric.")

        if quantity <= 0:
            return RiskDecision(False, "Quantity must be greater than zero.")

        if quantity > self.max_quantity:
            return RiskDecision(False, f"Quantity {quantity} exceeds max quantity {self.max_quantity}.")

        if order_type not in {"MARKET", "LIMIT"}:
            return RiskDecision(False, f"Unsupported order type: {order_type}")

        if order_type == "LIMIT" and intent.limit_price is None:
            return RiskDecision(False, "Limit order requires limit_price.")

        if last_price is None:
            return RiskDecision(False, "No last price available for notional check.")

        notional = quantity * float(last_price)

        if notional > self.max_notional:
            return RiskDecision(False, f"Order notional ${notional:,.2f} exceeds max ${self.max_notional:,.2f}.")

        if mode == "live" and not self.live_trading_enabled:
            return RiskDecision(False, "Live trading is disabled.")

        clean_intent = TradeIntent(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            limit_price=float(intent.limit_price) if intent.limit_price is not None else None,
            reason=str(intent.reason or ""),
            source=str(intent.source or "manual"),
        )

        return RiskDecision(True, "Approved.", clean_intent)