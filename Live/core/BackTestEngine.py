from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pandas as pd

if TYPE_CHECKING:
    from core.StrategyEngine import StrategySignal


@dataclass
class BacktestTrade:
    entry_time: Any
    exit_time: Any
    entry_price: float
    exit_price: float
    quantity: int
    pnl: float
    return_pct: float
    bars_held: int
    entry_commission: float = 0.0
    exit_commission: float = 0.0
    slippage_cost: float = 0.0
    total_costs: float = 0.0


@dataclass
class BacktestResult:
    initial_cash: float
    final_cash: float
    final_equity: float
    total_return_pct: float
    total_pnl: float
    max_drawdown_pct: float
    win_rate_pct: float
    trade_count: int
    winning_trades: int
    losing_trades: int
    trades: list[BacktestTrade] = field(default_factory=list)
    equity_curve: pd.DataFrame = field(default_factory=pd.DataFrame)
    errors: list[str] = field(default_factory=list)
    execution_mode: str = "next_open"
    commission_per_order: float = 0.0
    slippage_bps: float = 0.0
    total_commission: float = 0.0
    total_slippage: float = 0.0
    unfilled_signal_count: int = 0


class BackTestEngine:
    """
    Simple long-only backtest engine.

    Current rules:
        BUY opens a long position if flat.
        SELL closes the long position if open.
        No shorts yet.
        Signals execute at the next bar open by default.
        Optional commission and adverse slippage are included in net PnL.
        One fixed quantity per trade.
    """

    def run(
        self,
        bars: pd.DataFrame,
        signals: list[StrategySignal],
        initial_cash: float = 100_000.0,
        quantity: int = 1,
        execution_mode: str = "next_open",
        commission_per_order: float = 0.0,
        slippage_bps: float = 0.0,
    ) -> BacktestResult:
        errors: list[str] = []

        try:
            initial_cash = float(initial_cash)
        except Exception:
            initial_cash = 100_000.0
            errors.append("Invalid initial cash. Used 100000.")

        try:
            quantity = int(quantity)
        except Exception:
            quantity = 1
            errors.append("Invalid quantity. Used 1.")

        if initial_cash <= 0:
            initial_cash = 100_000.0
            errors.append("Initial cash must be greater than zero. Used 100000.")

        if quantity <= 0:
            quantity = 1
            errors.append("Quantity must be greater than zero. Used 1.")

        execution_mode = str(execution_mode or "next_open").strip().lower()
        if execution_mode not in {"next_open", "same_close"}:
            execution_mode = "next_open"
            errors.append("Invalid execution mode. Used next_open.")

        try:
            commission_per_order = float(commission_per_order)
        except Exception:
            commission_per_order = 0.0
            errors.append("Invalid commission per order. Used 0.")
        if commission_per_order < 0:
            commission_per_order = 0.0
            errors.append("Commission per order cannot be negative. Used 0.")

        try:
            slippage_bps = float(slippage_bps)
        except Exception:
            slippage_bps = 0.0
            errors.append("Invalid slippage basis points. Used 0.")
        if slippage_bps < 0:
            slippage_bps = 0.0
            errors.append("Slippage basis points cannot be negative. Used 0.")

        if bars is None or bars.empty:
            return BacktestResult(
                initial_cash=initial_cash,
                final_cash=initial_cash,
                final_equity=initial_cash,
                total_return_pct=0.0,
                total_pnl=0.0,
                max_drawdown_pct=0.0,
                win_rate_pct=0.0,
                trade_count=0,
                winning_trades=0,
                losing_trades=0,
                errors=["No bars available."],
                execution_mode=execution_mode,
                commission_per_order=commission_per_order,
                slippage_bps=slippage_bps,
            )

        clean_bars = self._clean_bars(bars)

        if clean_bars.empty:
            return BacktestResult(
                initial_cash=initial_cash,
                final_cash=initial_cash,
                final_equity=initial_cash,
                total_return_pct=0.0,
                total_pnl=0.0,
                max_drawdown_pct=0.0,
                win_rate_pct=0.0,
                trade_count=0,
                winning_trades=0,
                losing_trades=0,
                errors=["No valid bars available."],
                execution_mode=execution_mode,
                commission_per_order=commission_per_order,
                slippage_bps=slippage_bps,
            )

        signal_map: dict[int, list[StrategySignal]] = {}
        execution_lag = 1 if execution_mode == "next_open" else 0
        unfilled_signal_count = 0
        for signal in signals or []:
            execution_index = int(signal.index) + execution_lag
            if execution_index >= len(clean_bars):
                unfilled_signal_count += 1
                continue
            signal_map.setdefault(execution_index, []).append(signal)

        cash = initial_cash
        position_qty = 0
        entry_price: float | None = None
        entry_time: Any = None
        entry_index: int | None = None
        entry_commission = 0.0
        entry_slippage = 0.0
        total_commission = 0.0
        total_slippage = 0.0

        trades: list[BacktestTrade] = []
        equity_rows: list[dict[str, Any]] = []

        for idx, row in clean_bars.iterrows():
            market_price = float(row["close"])
            execution_price = float(row["open"] if execution_mode == "next_open" else row["close"])
            bar_time = row["time"] if "time" in clean_bars.columns else idx

            for signal in signal_map.get(int(idx), []):
                side = str(signal.side).upper()
                fill_price = self._apply_slippage(execution_price, side, slippage_bps)
                slippage_cost = abs(fill_price - execution_price) * quantity

                if side == "BUY":
                    if position_qty != 0:
                        continue

                    cost = (fill_price * quantity) + commission_per_order

                    if cost > cash:
                        errors.append(
                            f"Insufficient cash for BUY at index {idx}: "
                            f"cost ${cost:,.2f}, cash ${cash:,.2f}"
                        )
                        continue

                    cash -= cost
                    position_qty = quantity
                    entry_price = fill_price
                    entry_time = bar_time
                    entry_index = int(idx)
                    entry_commission = commission_per_order
                    entry_slippage = slippage_cost
                    total_commission += commission_per_order
                    total_slippage += slippage_cost

                elif side == "SELL":
                    if position_qty <= 0 or entry_price is None:
                        continue

                    proceeds = (fill_price * position_qty) - commission_per_order
                    cash += proceeds
                    total_commission += commission_per_order
                    total_slippage += slippage_cost

                    pnl = (
                        (fill_price - entry_price) * position_qty
                        - entry_commission
                        - commission_per_order
                    )
                    entry_capital = (entry_price * position_qty) + entry_commission
                    return_pct = (
                        (pnl / entry_capital) * 100.0
                        if entry_capital
                        else 0.0
                    )
                    bars_held = int(idx) - int(entry_index or idx)

                    trades.append(
                        BacktestTrade(
                            entry_time=entry_time,
                            exit_time=bar_time,
                            entry_price=float(entry_price),
                            exit_price=fill_price,
                            quantity=int(position_qty),
                            pnl=float(pnl),
                            return_pct=float(return_pct),
                            bars_held=int(bars_held),
                            entry_commission=float(entry_commission),
                            exit_commission=float(commission_per_order),
                            slippage_cost=float(entry_slippage + slippage_cost),
                            total_costs=float(entry_commission + commission_per_order + entry_slippage + slippage_cost),
                        )
                    )

                    position_qty = 0
                    entry_price = None
                    entry_time = None
                    entry_index = None
                    entry_commission = 0.0
                    entry_slippage = 0.0

            market_value = position_qty * market_price
            equity = cash + market_value

            equity_rows.append(
                {
                    "time": bar_time,
                    "cash": float(cash),
                    "position_qty": int(position_qty),
                    "price": float(market_price),
                    "market_value": float(market_value),
                    "equity": float(equity),
                }
            )

        final_price = float(clean_bars.iloc[-1]["close"])
        final_equity = cash + (position_qty * final_price)

        equity_curve = pd.DataFrame(equity_rows)

        total_pnl = final_equity - initial_cash
        total_return_pct = (total_pnl / initial_cash) * 100.0 if initial_cash else 0.0

        max_drawdown_pct = self._max_drawdown_pct(equity_curve)

        winning_trades = sum(1 for trade in trades if trade.pnl > 0)
        losing_trades = sum(1 for trade in trades if trade.pnl < 0)
        trade_count = len(trades)

        win_rate_pct = (
            (winning_trades / trade_count) * 100.0
            if trade_count
            else 0.0
        )

        return BacktestResult(
            initial_cash=float(initial_cash),
            final_cash=float(cash),
            final_equity=float(final_equity),
            total_return_pct=float(total_return_pct),
            total_pnl=float(total_pnl),
            max_drawdown_pct=float(max_drawdown_pct),
            win_rate_pct=float(win_rate_pct),
            trade_count=int(trade_count),
            winning_trades=int(winning_trades),
            losing_trades=int(losing_trades),
            trades=trades,
            equity_curve=equity_curve,
            errors=errors,
            execution_mode=execution_mode,
            commission_per_order=float(commission_per_order),
            slippage_bps=float(slippage_bps),
            total_commission=float(total_commission),
            total_slippage=float(total_slippage),
            unfilled_signal_count=int(unfilled_signal_count),
        )

    def _apply_slippage(self, price: float, side: str, slippage_bps: float) -> float:
        adjustment = slippage_bps / 10_000.0
        if str(side).upper() == "BUY":
            return price * (1.0 + adjustment)
        if str(side).upper() == "SELL":
            return price * (1.0 - adjustment)
        return price

    def _clean_bars(self, bars: pd.DataFrame) -> pd.DataFrame:
        clean_bars = bars.copy()

        required = ["open", "high", "low", "close"]
        for col in required:
            if col not in clean_bars.columns:
                raise ValueError(f"Bars are missing column: {col}")

            clean_bars[col] = pd.to_numeric(clean_bars[col], errors="coerce")

        if "time" in clean_bars.columns:
            clean_bars["time"] = pd.to_datetime(
                clean_bars["time"],
                errors="coerce",
                format="mixed",
            )
            clean_bars = clean_bars.dropna(
                subset=["time", "open", "high", "low", "close"]
            ).copy()
        else:
            clean_bars = clean_bars.dropna(
                subset=["open", "high", "low", "close"]
            ).copy()

        clean_bars = clean_bars.reset_index(drop=True)
        return clean_bars

    def _max_drawdown_pct(self, equity_curve: pd.DataFrame) -> float:
        if equity_curve is None or equity_curve.empty:
            return 0.0

        if "equity" not in equity_curve.columns:
            return 0.0

        equity = pd.to_numeric(equity_curve["equity"], errors="coerce").dropna()

        if equity.empty:
            return 0.0

        running_max = equity.cummax()
        drawdown = (equity - running_max) / running_max.replace(0, pd.NA)
        min_drawdown = drawdown.min()

        if pd.isna(min_drawdown):
            return 0.0

        return float(min_drawdown * 100.0)

# BEGIN v24.6 direct producer wiring
try:
    from services.quant_schema.producer_runtime import wire_current_module
    wire_current_module(__name__, globals())
except Exception as _v24_6_direct_wiring_exc:
    print(f"[v24.6 direct producer wiring] disabled for {__name__}: {type(_v24_6_direct_wiring_exc).__name__}: {_v24_6_direct_wiring_exc}")
# END v24.6 direct producer wiring
