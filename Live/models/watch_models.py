from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import pandas as pd


ChartSource = Literal["live", "replay", "empty", "error"]


@dataclass
class WatchBarsView:
    """
    Prepared bar snapshot for the Watch chart.

    This object is intentionally plain data. It lets callbacks stop doing
    bar-cleaning, replay/live branching, and resampling inline.
    """

    source: ChartSource
    symbol: str
    display_timeframe: str
    full_bars: pd.DataFrame
    visible_bars: pd.DataFrame
    chart_bars: pd.DataFrame
    current_price: float | None
    updated_at: datetime | None
    current_index: int
    max_index: int
    chart_label: str
    error: str | None = None

    @property
    def is_empty(self) -> bool:
        return self.chart_bars is None or self.chart_bars.empty

    @property
    def is_replay(self) -> bool:
        return self.source == "replay"

    @property
    def is_live(self) -> bool:
        return self.source == "live"
