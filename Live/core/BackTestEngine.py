from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

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


class BackTestEngine:
    """
    Simple long-only backtest engine.

    Current rules:
        BUY opens a long position if flat.
        SELL closes the long position if open.
        No shorts yet.
        No commissions/slippage yet.
        One fixed quantity per trade.
    """

    def run(
        self,
        bars: pd.DataFrame,
        signals: list[StrategySignal],
        initial_cash: float = 100_000.0,
        quantity: int = 1,
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
            )

        signal_map: dict[int, list[StrategySignal]] = {}
        for signal in signals or []:
            signal_map.setdefault(int(signal.index), []).append(signal)

        cash = initial_cash
        position_qty = 0
        entry_price: float | None = None
        entry_time: Any = None
        entry_index: int | None = None

        trades: list[BacktestTrade] = []
        equity_rows: list[dict[str, Any]] = []

        for idx, row in clean_bars.iterrows():
            price = float(row["close"])
            bar_time = row["time"] if "time" in clean_bars.columns else idx

            for signal in signal_map.get(int(idx), []):
                side = str(signal.side).upper()

                if side == "BUY":
                    if position_qty != 0:
                        continue

                    cost = price * quantity

                    if cost > cash:
                        errors.append(
                            f"Insufficient cash for BUY at index {idx}: "
                            f"cost ${cost:,.2f}, cash ${cash:,.2f}"
                        )
                        continue

                    cash -= cost
                    position_qty = quantity
                    entry_price = price
                    entry_time = bar_time
                    entry_index = int(idx)

                elif side == "SELL":
                    if position_qty <= 0 or entry_price is None:
                        continue

                    proceeds = price * position_qty
                    cash += proceeds

                    pnl = (price - entry_price) * position_qty
                    return_pct = (
                        ((price - entry_price) / entry_price) * 100.0
                        if entry_price
                        else 0.0
                    )
                    bars_held = int(idx) - int(entry_index or idx)

                    trades.append(
                        BacktestTrade(
                            entry_time=entry_time,
                            exit_time=bar_time,
                            entry_price=float(entry_price),
                            exit_price=price,
                            quantity=int(position_qty),
                            pnl=float(pnl),
                            return_pct=float(return_pct),
                            bars_held=int(bars_held),
                        )
                    )

                    position_qty = 0
                    entry_price = None
                    entry_time = None
                    entry_index = None

            market_value = position_qty * price
            equity = cash + market_value

            equity_rows.append(
                {
                    "time": bar_time,
                    "cash": float(cash),
                    "position_qty": int(position_qty),
                    "price": float(price),
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
        )

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
