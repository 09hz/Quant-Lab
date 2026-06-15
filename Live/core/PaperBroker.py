from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional

import pandas as pd

from core.RiskGuard import TradeIntent


@dataclass
class PaperOrder:
    order_id: int
    symbol: str
    side: str
    quantity: float
    order_type: str
    status: str
    submitted_at: datetime
    filled_at: Optional[datetime] = None
    limit_price: Optional[float] = None
    fill_price: Optional[float] = None
    reason: str = ""
    source: str = "manual"


@dataclass
class PaperPosition:
    symbol: str
    quantity: float = 0.0
    avg_price: float = 0.0
    realized_pnl: float = 0.0
    short_margin_reserved: float = 0.0


@dataclass
class PaperFill:
    order_id: int
    symbol: str
    side: str
    quantity: float
    price: float
    timestamp: datetime
    realized_pnl: float = 0.0
    reason: str = ""
    source: str = "manual"


class PaperBroker:
    """
    Local simulated broker.

    quantity > 0 means long.
    quantity < 0 means short.

    Short model:
    - Opening/adding a short reserves paper cash instead of increasing cash.
    - Covering releases reserved collateral and applies realized PnL.
    - Equity = cash + long value + short reserve + short unrealized PnL.
    """

    def __init__(
        self,
        starting_cash: float = 100_000,
        commission_per_order: float = 0.0,
        slippage_bps: float = 0.0,
    ):
        self.starting_cash = float(starting_cash)
        self.cash = float(starting_cash)
        self.commission_per_order = float(commission_per_order)
        self.slippage_bps = float(slippage_bps)

        self._next_order_id = 1
        self.orders: list[PaperOrder] = []
        self.fills: list[PaperFill] = []
        self.positions: dict[str, PaperPosition] = {}

    def reset(self) -> None:
        self.cash = self.starting_cash
        self._next_order_id = 1
        self.orders.clear()
        self.fills.clear()
        self.positions.clear()

    def get_position_quantity(self, symbol: str) -> float:
        symbol = str(symbol or "").upper().strip()
        position = self.positions.get(symbol)
        if position is None:
            return 0.0
        return float(position.quantity)

    def submit_order(
        self,
        intent: TradeIntent,
        last_price: float,
        timestamp: Optional[datetime] = None,
    ) -> PaperOrder:
        if timestamp is None:
            timestamp = datetime.now()

        order = PaperOrder(
            order_id=self._next_order_id,
            symbol=intent.symbol.upper().strip(),
            side=intent.side.upper().strip(),
            quantity=float(intent.quantity),
            order_type=intent.order_type.upper().strip(),
            limit_price=float(intent.limit_price) if intent.limit_price is not None else None,
            status="SUBMITTED",
            submitted_at=timestamp,
            reason=intent.reason,
            source=intent.source,
        )

        self._next_order_id += 1
        self.orders.append(order)

        try:
            self._try_fill_order(order, last_price=last_price, timestamp=timestamp)
        except Exception as exc:
            order.status = "REJECTED"
            order.reason = f"{order.reason} | Rejected: {exc}".strip(" |")
            raise

        return order

    def _try_fill_order(self, order: PaperOrder, last_price: float, timestamp: datetime) -> None:
        if order.status != "SUBMITTED":
            return

        fill_price = self._get_fill_price(order, last_price)
        if fill_price is None:
            return

        realized_pnl = self._apply_fill(
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=fill_price,
        )

        order.status = "FILLED"
        order.filled_at = timestamp
        order.fill_price = fill_price

        self.fills.append(
            PaperFill(
                order_id=order.order_id,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                price=fill_price,
                timestamp=timestamp,
                realized_pnl=realized_pnl,
                reason=order.reason,
                source=order.source,
            )
        )

    def _get_fill_price(self, order: PaperOrder, last_price: float) -> Optional[float]:
        price = float(last_price)

        if order.order_type == "MARKET":
            return self._apply_slippage(price, order.side)

        if order.order_type == "LIMIT":
            if order.limit_price is None:
                return None

            limit_price = float(order.limit_price)

            if order.side == "BUY" and price <= limit_price:
                return limit_price

            if order.side == "SELL" and price >= limit_price:
                return limit_price

            return None

        return None

    def _apply_slippage(self, price: float, side: str) -> float:
        adjustment = self.slippage_bps / 10_000

        if side == "BUY":
            return price * (1 + adjustment)

        if side == "SELL":
            return price * (1 - adjustment)

        return price

    def _release_short_reserve(self, position: PaperPosition, cover_qty: float) -> float:
        old_short_qty = abs(float(position.quantity))
        cover_qty = float(cover_qty)

        if old_short_qty <= 0 or cover_qty <= 0:
            return 0.0

        release_ratio = min(1.0, cover_qty / old_short_qty)
        released = float(position.short_margin_reserved) * release_ratio
        position.short_margin_reserved = max(0.0, float(position.short_margin_reserved) - released)
        return released

    def _apply_fill(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
    ) -> float:
        symbol = symbol.upper().strip()
        side = side.upper().strip()
        quantity = float(quantity)
        price = float(price)
        commission = float(self.commission_per_order)

        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")

        position = self.positions.get(symbol)
        if position is None:
            position = PaperPosition(symbol=symbol)
            self.positions[symbol] = position

        realized_pnl = 0.0
        old_qty = float(position.quantity)

        if side == "BUY":
            # BUY while short covers first. Any remaining buy opens long.
            if old_qty < 0:
                old_short_qty = abs(old_qty)
                cover_qty = min(quantity, old_short_qty)

                released_reserve = self._release_short_reserve(position, cover_qty)
                cover_pnl = (position.avg_price - price) * cover_qty

                realized_pnl += cover_pnl
                position.realized_pnl += cover_pnl
                self.cash += released_reserve + cover_pnl - commission

                position.quantity = old_qty + cover_qty
                remaining_buy_qty = quantity - cover_qty

                if position.quantity == 0:
                    position.avg_price = 0.0
                    position.short_margin_reserved = 0.0

                if remaining_buy_qty > 0:
                    long_cost = remaining_buy_qty * price
                    if long_cost > self.cash:
                        raise ValueError(
                            f"Insufficient paper cash after covering short. "
                            f"Needed ${long_cost:,.2f}, available ${self.cash:,.2f}."
                        )

                    position.quantity = remaining_buy_qty
                    position.avg_price = price
                    position.short_margin_reserved = 0.0
                    self.cash -= long_cost

                return realized_pnl

            # BUY while flat/long opens or increases long.
            cash_needed = quantity * price + commission
            if cash_needed > self.cash:
                raise ValueError(
                    f"Insufficient paper cash. Needed ${cash_needed:,.2f}, available ${self.cash:,.2f}."
                )

            old_cost = old_qty * position.avg_price
            new_cost = quantity * price

            position.quantity = old_qty + quantity
            position.avg_price = (old_cost + new_cost) / position.quantity if position.quantity else 0.0
            position.short_margin_reserved = 0.0
            self.cash -= cash_needed
            return realized_pnl

        if side == "SELL":
            # SELL while long closes long first. Any remaining sell opens short.
            if old_qty > 0:
                close_qty = min(quantity, old_qty)

                long_pnl = (price - position.avg_price) * close_qty
                proceeds = close_qty * price

                realized_pnl += long_pnl
                position.realized_pnl += long_pnl
                self.cash += proceeds - commission

                position.quantity = old_qty - close_qty
                remaining_sell_qty = quantity - close_qty

                if position.quantity == 0:
                    position.avg_price = 0.0

                if remaining_sell_qty > 0:
                    short_reserve_needed = remaining_sell_qty * price

                    if short_reserve_needed > self.cash:
                        raise ValueError(
                            f"Insufficient paper cash to reserve short collateral. "
                            f"Needed ${short_reserve_needed:,.2f}, available ${self.cash:,.2f}."
                        )

                    position.quantity = -remaining_sell_qty
                    position.avg_price = price
                    position.short_margin_reserved = short_reserve_needed
                    self.cash -= short_reserve_needed

                return realized_pnl

            # SELL while flat/short opens or increases short.
            old_short_qty = abs(old_qty)
            old_short_value = old_short_qty * position.avg_price
            new_short_value = quantity * price
            new_short_qty = old_short_qty + quantity

            short_reserve_needed = quantity * price + commission

            if short_reserve_needed > self.cash:
                raise ValueError(
                    f"Insufficient paper cash to reserve short collateral. "
                    f"Needed ${short_reserve_needed:,.2f}, available ${self.cash:,.2f}."
                )

            position.quantity = -new_short_qty
            position.avg_price = (
                (old_short_value + new_short_value) / new_short_qty
                if new_short_qty
                else 0.0
            )
            position.short_margin_reserved += quantity * price
            self.cash -= short_reserve_needed
            return realized_pnl

        raise ValueError(f"Unsupported side: {side}")

    def mark_to_market_value(self, prices: dict[str, float]) -> float:
        total = float(self.cash)

        for symbol, position in self.positions.items():
            price = prices.get(symbol)
            if price is None:
                price = position.avg_price

            qty = float(position.quantity)
            price = float(price)

            if qty > 0:
                total += qty * price

            elif qty < 0:
                short_qty = abs(qty)
                unrealized_pnl = (float(position.avg_price) - price) * short_qty
                total += float(position.short_margin_reserved) + unrealized_pnl

        return total

    def positions_df(self) -> pd.DataFrame:
        rows = [asdict(pos) for pos in self.positions.values()]
        return pd.DataFrame(rows)

    def orders_df(self) -> pd.DataFrame:
        rows = [asdict(order) for order in self.orders]
        return pd.DataFrame(rows)

    def fills_df(self) -> pd.DataFrame:
        rows = [asdict(fill) for fill in self.fills]
        return pd.DataFrame(rows)

    def summary(self, prices: Optional[dict[str, float]] = None) -> dict:
        prices = prices or {}

        short_margin_reserved = sum(
            float(p.short_margin_reserved)
            for p in self.positions.values()
            if float(p.quantity) < 0
        )

        return {
            "starting_cash": self.starting_cash,
            "cash": self.cash,
            "short_margin_reserved": short_margin_reserved,
            "equity": self.mark_to_market_value(prices),
            "open_positions": len([p for p in self.positions.values() if p.quantity != 0]),
            "orders": len(self.orders),
            "fills": len(self.fills),
        }
