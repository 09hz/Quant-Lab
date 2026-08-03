from __future__ import annotations

from datetime import datetime
import math
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
        self._active_review: Optional[dict] = None
        self._review_activated_equity: Optional[float] = None
        self._review_peak_equity: Optional[float] = None
        self._review_day = None
        self._review_day_start_equity: Optional[float] = None
        self._review_last_timestamp: Optional[datetime] = None

    def reset(self) -> None:
        self.broker.reset()
        self._reset_review_baselines()

    def set_starting_cash(self, value: float, *, reset_account: bool = True) -> float:
        starting_cash = self.broker.set_starting_cash(value, reset_account=reset_account)
        self._reset_review_baselines()
        return starting_cash

    @staticmethod
    def _normalize_review_policy(policy: Optional[dict] = None) -> dict:
        defaults = {
            "max_position_pct": 20.0,
            "max_daily_loss_pct": 2.0,
            "max_drawdown_pct": 10.0,
            "max_orders_per_day": 10,
            "allow_short": False,
        }
        supplied = dict(policy or {})

        def bounded_float(name: str, minimum: float, maximum: float) -> float:
            try:
                value = float(supplied.get(name, defaults[name]))
            except (TypeError, ValueError):
                value = float(defaults[name])
            if not math.isfinite(value):
                value = float(defaults[name])
            return max(minimum, min(maximum, value))

        try:
            max_orders = int(supplied.get("max_orders_per_day", defaults["max_orders_per_day"]))
        except (TypeError, ValueError):
            max_orders = int(defaults["max_orders_per_day"])

        return {
            "max_position_pct": bounded_float("max_position_pct", 0.1, 100.0),
            "max_daily_loss_pct": bounded_float("max_daily_loss_pct", 0.1, 100.0),
            "max_drawdown_pct": bounded_float("max_drawdown_pct", 0.1, 100.0),
            "max_orders_per_day": max(1, min(10_000, max_orders)),
            "allow_short": supplied.get("allow_short", defaults["allow_short"]) is True,
        }

    def _review_equity(self, symbol: str = "", last_price: Optional[float] = None) -> float:
        prices = None
        if symbol and last_price is not None:
            prices = {str(symbol).upper().strip(): float(last_price)}
        return float(self.broker.summary(prices).get("equity", self.broker.cash) or 0.0)

    def _reset_review_baselines(self, timestamp: Optional[datetime] = None) -> None:
        if self._active_review is None:
            return
        now = timestamp or datetime.now()
        symbol = str(self._active_review.get("symbol") or "")
        equity = self._review_equity(symbol)
        self._review_activated_equity = equity
        self._review_peak_equity = equity
        self._review_day = now.date()
        self._review_day_start_equity = equity
        self._review_last_timestamp = now

    def activate_review(
        self,
        packet: dict,
        *,
        risk_policy: Optional[dict] = None,
        timestamp: Optional[datetime] = None,
    ) -> dict:
        """Activate a promoted candidate for manual, guarded paper review."""
        if not isinstance(packet, dict):
            raise ValueError("Paper review packet must be a dictionary.")
        if str(packet.get("promotion_decision") or "").lower() != "promote":
            raise ValueError("Only promoted candidates can enter paper review.")
        if packet.get("auto_execute") is True:
            raise ValueError("Automatic execution is not allowed in paper review.")

        symbol = str(packet.get("symbol") or "").upper().strip()
        candidate_id = str(packet.get("candidate_id") or "").strip()
        if not symbol or not candidate_id:
            raise ValueError("Paper review requires a symbol and candidate ID.")

        merged_policy = dict(packet.get("risk_policy") or {})
        merged_policy.update(dict(risk_policy or {}))
        now = timestamp or datetime.now()
        equity = self._review_equity(symbol)
        self._active_review = {
            "review_id": str(packet.get("review_id") or candidate_id),
            "candidate_id": candidate_id,
            "symbol": symbol,
            "promotion_decision": "promote",
            "review_status": "active_paper_review",
            "activated_at": now.isoformat(),
            "auto_execute": False,
            "risk_policy": self._normalize_review_policy(merged_policy),
        }
        self._review_activated_equity = equity
        self._review_peak_equity = equity
        self._review_day = now.date()
        self._review_day_start_equity = equity
        self._review_last_timestamp = now
        return self.review_status()

    def deactivate_review(self) -> dict:
        self._active_review = None
        self._review_activated_equity = None
        self._review_peak_equity = None
        self._review_day = None
        self._review_day_start_equity = None
        self._review_last_timestamp = None
        return {"review_status": "inactive", "auto_execute": False}

    def _review_orders_today(self, timestamp: datetime) -> int:
        return sum(
            1
            for order in self.broker.orders
            if getattr(order, "submitted_at", timestamp).date() == timestamp.date()
        )

    def _review_metrics(
        self,
        *,
        timestamp: datetime,
        symbol: str,
        last_price: Optional[float],
    ) -> dict:
        self._review_last_timestamp = timestamp
        equity = self._review_equity(symbol, last_price)
        if self._review_day != timestamp.date():
            self._review_day = timestamp.date()
            self._review_day_start_equity = equity

        if self._review_peak_equity is None:
            self._review_peak_equity = equity
        self._review_peak_equity = max(float(self._review_peak_equity), equity)

        day_start = float(self._review_day_start_equity or equity or 1.0)
        peak = float(self._review_peak_equity or equity or 1.0)
        daily_loss_pct = max(0.0, (day_start - equity) / day_start * 100.0) if day_start > 0 else 0.0
        drawdown_pct = max(0.0, (peak - equity) / peak * 100.0) if peak > 0 else 0.0
        return {
            "activated_equity": float(self._review_activated_equity or 0.0),
            "current_equity": equity,
            "daily_loss_pct": daily_loss_pct,
            "drawdown_pct": drawdown_pct,
            "orders_today": self._review_orders_today(timestamp),
        }

    def review_status(
        self,
        prices: Optional[dict[str, float]] = None,
        timestamp: Optional[datetime] = None,
    ) -> dict:
        if self._active_review is None:
            return {"review_status": "inactive", "auto_execute": False}

        symbol = str(self._active_review.get("symbol") or "")
        last_price = (prices or {}).get(symbol)
        metrics = self._review_metrics(
            timestamp=timestamp or self._review_last_timestamp or datetime.now(),
            symbol=symbol,
            last_price=last_price,
        )
        return {**self._active_review, **metrics}

    def _is_review_risk_reducing(self, intent: TradeIntent, current_position: float) -> bool:
        side = str(intent.side or "").upper().strip()
        quantity = float(intent.quantity or 0.0)
        if current_position > 0 and side == "SELL" and not self._is_short_sell_intent(intent):
            return quantity <= current_position
        if current_position < 0 and side == "BUY":
            return quantity <= abs(current_position)
        return False

    def _validate_active_review(
        self,
        *,
        intent: TradeIntent,
        last_price: float,
        timestamp: datetime,
        current_position: float,
    ) -> Optional[RiskDecision]:
        if self._active_review is None:
            return None

        symbol = str(intent.symbol or "").upper().strip()
        source = str(getattr(intent, "source", "") or "manual").lower()
        if not source.startswith("manual"):
            return self._reject(intent, "Paper review requires explicit manual orders; automatic execution is disabled.")

        review_symbol = str(self._active_review.get("symbol") or "")
        risk_reducing = self._is_review_risk_reducing(intent, current_position)
        if risk_reducing:
            return None
        if symbol != review_symbol:
            return self._reject(intent, f"Paper review symbol is locked to {review_symbol}.")

        policy = dict(self._active_review.get("risk_policy") or {})
        if self._is_short_sell_intent(intent) and not policy.get("allow_short", False):
            return self._reject(intent, "Short selling is disabled by the paper review risk policy.")

        metrics = self._review_metrics(
            timestamp=timestamp,
            symbol=review_symbol,
            last_price=last_price,
        )
        if metrics["orders_today"] >= int(policy["max_orders_per_day"]):
            return self._reject(intent, "Paper review order limit reached for today.")
        if metrics["daily_loss_pct"] >= float(policy["max_daily_loss_pct"]):
            return self._reject(intent, "Paper review daily loss limit reached; only risk-reducing exits are allowed.")
        if metrics["drawdown_pct"] >= float(policy["max_drawdown_pct"]):
            return self._reject(intent, "Paper review drawdown limit reached; only risk-reducing exits are allowed.")

        side = str(intent.side or "").upper().strip()
        quantity = float(intent.quantity or 0.0)
        projected_position = current_position + quantity if side == "BUY" else current_position - quantity
        max_position_value = float(self.broker.starting_cash) * float(policy["max_position_pct"]) / 100.0
        if abs(projected_position) * float(last_price) > max_position_value:
            return self._reject(
                intent,
                f"Paper review position limit is {policy['max_position_pct']:g}% of starting cash.",
            )
        return None

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

    def _approve_review_exit(self, intent: TradeIntent) -> RiskDecision:
        order_type = str(intent.order_type or "MARKET").upper().strip()
        if order_type not in {"MARKET", "LIMIT"}:
            return self._reject(intent, f"Unsupported order type: {order_type}")
        if order_type == "LIMIT" and intent.limit_price is None:
            return self._reject(intent, "Limit order requires limit_price.")

        clean_intent = TradeIntent(
            symbol=str(intent.symbol or "").upper().strip(),
            side=str(intent.side or "").upper().strip(),
            quantity=float(intent.quantity),
            order_type=order_type,
            limit_price=float(intent.limit_price) if intent.limit_price is not None else None,
            reason=str(intent.reason or ""),
            source=str(intent.source or "manual"),
        )
        try:
            return RiskDecision(
                approved=True,
                message="Approved risk-reducing paper review exit.",
                intent=clean_intent,
            )
        except TypeError:
            return RiskDecision(True, "Approved risk-reducing paper review exit.", clean_intent)

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
        order_timestamp = timestamp or datetime.now()
        current_position = self._current_position_qty(intent.symbol)

        position_rejection = self._validate_position_action(
            intent=intent,
            current_position=current_position,
            allow_short=allow_short,
        )

        if position_rejection is not None:
            return position_rejection, None

        review_rejection = self._validate_active_review(
            intent=intent,
            last_price=last_price,
            timestamp=order_timestamp,
            current_position=current_position,
        )
        if review_rejection is not None:
            return review_rejection, None

        review_exit = (
            self._active_review is not None
            and self._is_review_risk_reducing(intent, current_position)
        )
        if review_exit:
            decision = self._approve_review_exit(intent)
        else:
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
            timestamp=order_timestamp,
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
