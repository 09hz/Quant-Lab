from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


class PaperStateCache:
    """
    Durable cache for paper trading data.

    Saves:
    - summary snapshot
    - positions
    - orders
    - fills
    """

    def __init__(self, cache_dir: str | Path = "cache/paper"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.snapshot_path = self.cache_dir / "paper_state.json"
        self.positions_path = self.cache_dir / "positions.csv"
        self.orders_path = self.cache_dir / "orders.csv"
        self.fills_path = self.cache_dir / "fills.csv"

    def save_from_service(self, paper_trading_service, prices: dict[str, float] | None = None) -> None:
        if paper_trading_service is None:
            return

        prices = prices or {}

        try:
            summary = paper_trading_service.summary(prices=prices)
        except Exception:
            summary = {}

        try:
            positions = paper_trading_service.positions_df()
        except Exception:
            positions = pd.DataFrame()

        try:
            orders = paper_trading_service.orders_df()
        except Exception:
            orders = pd.DataFrame()

        try:
            fills = paper_trading_service.fills_df()
        except Exception:
            fills = pd.DataFrame()

        self._write_df(positions, self.positions_path)
        self._write_df(orders, self.orders_path)
        self._write_df(fills, self.fills_path)

        snapshot = {
            "saved_at": datetime.now().isoformat(),
            "summary": summary,
            "files": {
                "positions": str(self.positions_path),
                "orders": str(self.orders_path),
                "fills": str(self.fills_path),
            },
        }

        self._atomic_json_write(self.snapshot_path, snapshot)

    def load_snapshot(self) -> dict[str, Any]:
        if not self.snapshot_path.exists():
            return {}

        try:
            with self.snapshot_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def load_positions_df(self) -> pd.DataFrame:
        return self._read_df(self.positions_path)

    def load_orders_df(self) -> pd.DataFrame:
        return self._read_df(self.orders_path)

    def load_fills_df(self) -> pd.DataFrame:
        return self._read_df(self.fills_path)

    def clear(self) -> None:
        for path in [
            self.snapshot_path,
            self.positions_path,
            self.orders_path,
            self.fills_path,
        ]:
            try:
                if path.exists():
                    path.unlink()
            except Exception:
                pass

    def _write_df(self, df: pd.DataFrame | None, path: Path) -> None:
        if df is None:
            df = pd.DataFrame()

        tmp_path = path.with_suffix(path.suffix + ".tmp")
        df.to_csv(tmp_path, index=False)
        os.replace(tmp_path, path)

    def _read_df(self, path: Path) -> pd.DataFrame:
        if not path.exists():
            return pd.DataFrame()

        try:
            return pd.read_csv(path)
        except Exception:
            return pd.DataFrame()

    def _atomic_json_write(self, path: Path, payload: dict[str, Any]) -> None:
        tmp_path = path.with_suffix(path.suffix + ".tmp")

        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)

        os.replace(tmp_path, path)
