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

    Negative position quantity means a paper short position:
        quantity =  10 -> long 10
        quantity =   0 -> flat
        quantity = -10 -> short 10
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

        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")

        position = self.positions.get(symbol)
        if position is None:
            position = PaperPosition(symbol=symbol)
            self.positions[symbol] = position

        realized_pnl = 0.0
        old_qty = float(position.quantity)

        if side == "BUY":
            cash_needed = quantity * price + self.commission_per_order
            if cash_needed > self.cash:
                raise ValueError(
                    f"Insufficient paper cash. Needed ${cash_needed:,.2f}, available ${self.cash:,.2f}."
                )

            if old_qty < 0:
                cover_qty = min(quantity, abs(old_qty))
                realized_pnl += (position.avg_price - price) * cover_qty
                position.realized_pnl += realized_pnl

                self.cash -= cover_qty * price + self.commission_per_order
                position.quantity = old_qty + cover_qty

                remaining_buy_qty = quantity - cover_qty

                if remaining_buy_qty > 0:
                    position.quantity = remaining_buy_qty
                    position.avg_price = price
                    self.cash -= remaining_buy_qty * price
                elif position.quantity == 0:
                    position.avg_price = 0.0

                return realized_pnl

            old_cost = old_qty * position.avg_price
            new_cost = quantity * price

            position.quantity = old_qty + quantity
            position.avg_price = (old_cost + new_cost) / position.quantity if position.quantity else 0.0
            self.cash -= cash_needed
            return realized_pnl

        if side == "SELL":
            if old_qty > 0:
                close_qty = min(quantity, old_qty)
                proceeds = close_qty * price - self.commission_per_order
                realized_pnl += (price - position.avg_price) * close_qty - self.commission_per_order

                self.cash += proceeds
                position.quantity = old_qty - close_qty
                position.realized_pnl += realized_pnl

                remaining_sell_qty = quantity - close_qty

                if remaining_sell_qty > 0:
                    position.quantity = -remaining_sell_qty
                    position.avg_price = price
                    self.cash += remaining_sell_qty * price
                elif position.quantity == 0:
                    position.avg_price = 0.0

                return realized_pnl

            short_proceeds = quantity * price - self.commission_per_order

            old_short_qty = abs(old_qty)
            old_short_value = old_short_qty * position.avg_price
            new_short_value = quantity * price
            new_short_qty = old_short_qty + quantity

            position.quantity = -new_short_qty
            position.avg_price = (old_short_value + new_short_value) / new_short_qty if new_short_qty else 0.0
            self.cash += short_proceeds
            return realized_pnl

        raise ValueError(f"Unsupported side: {side}")

    def mark_to_market_value(self, prices: dict[str, float]) -> float:
        total = self.cash

        for symbol, position in self.positions.items():
            price = prices.get(symbol)
            if price is None:
                price = position.avg_price

            qty = float(position.quantity)
            price = float(price)

            if qty >= 0:
                total += qty * price
            else:
                # Liability to buy back borrowed shares.
                total += qty * price

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

        return {
            "starting_cash": self.starting_cash,
            "cash": self.cash,
            "equity": self.mark_to_market_value(prices),
            "open_positions": len([p for p in self.positions.values() if p.quantity != 0]),
            "orders": len(self.orders),
            "fills": len(self.fills),
        }
